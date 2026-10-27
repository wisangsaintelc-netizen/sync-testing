from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
import re
from threading import Lock
from typing import Callable

from bapps_sync_agent.domain.errors import SyncInterrupted, SyncNotFound, SyncPaused
from bapps_sync_agent.domain.read_recipes import RecipeValidationError
from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.domain.runs import ActiveRun
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.infrastructure.local_sync_log import LocalSyncLogRepository
from bapps_sync_agent.infrastructure.run_state_store import RunStateStore
from bapps_sync_agent.syncs.registry import SynchronizerRegistry


class SyncRunner:
    _MAX_ERROR_DETAIL = 1_200
    _URL_CREDENTIALS = re.compile(r"(?i)([a-z][a-z0-9+.-]*://[^\s:/@]+:)([^@\s/]+)(@)")
    _SECRET_VALUE = re.compile(
        r"(?i)\b(password|pwd|pass|token|secret|api[_-]?key)\b(\s*[:=]\s*)([^\s;,&]+)"
    )
    _CODE_PREFIX = re.compile(r"^([A-Z][A-Z0-9_]{2,127}):\s*(.+)$")

    def __init__(
        self,
        registry: SynchronizerRegistry,
        outbox: Outbox,
        is_enabled: Callable[[str], bool],
        run_state: RunStateStore | None = None,
        local_log: LocalSyncLogRepository | None = None,
    ) -> None:
        self._registry = registry
        self._outbox = outbox
        self._is_enabled = is_enabled
        self._run_state = run_state
        self._local_log = local_log
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bapps-sync-worker")
        self._active: dict[str, ActiveRun] = {}
        self._lock = Lock()

    def submit(self, sync_code: str, trigger: str, run_id: str | None = None) -> tuple[str, Future[SyncResult]]:
        active_run = self._reserve(sync_code, trigger, run_id)
        return active_run.context.run_id, self._executor.submit(self._execute, active_run)

    def request_stop(self, run_id: str) -> bool:
        with self._lock:
            run = self._active.get(run_id)
            if run is None:
                return False
            run.stop_event.set()
            return True

    def active_runs(self) -> list[dict[str, str]]:
        with self._lock:
            return [
                {
                    "run_id": run.context.run_id,
                    "sync_code": run.context.sync_code,
                    "status": "stopping" if run.stop_event.is_set() else "running",
                    "started_at": run.started_at.isoformat(),
                }
                for run in self._active.values()
            ]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=False)

    def _reserve(self, sync_code: str, trigger: str, run_id: str | None = None) -> ActiveRun:
        if not self._is_enabled(sync_code):
            raise SyncPaused(sync_code)
        self._registry.resolve(sync_code)
        with self._lock:
            if any(run.context.sync_code == sync_code for run in self._active.values()):
                raise RuntimeError("SYNC_ALREADY_RUNNING")
            active_run = ActiveRun.create(sync_code, trigger, datetime.now(UTC), run_id)
            if self._run_state is not None:
                self._run_state.mark_started({
                    "run_id": active_run.context.run_id,
                    "correlation_id": active_run.context.correlation_id,
                    "sync_code": active_run.context.sync_code,
                    "trigger": active_run.context.trigger,
                    "started_at": active_run.started_at.isoformat(),
                })
            self._active[active_run.context.run_id] = active_run
            return active_run

    def _execute(self, active_run: ActiveRun) -> SyncResult:
        context = active_run.context
        started = datetime.now(UTC)
        status = "failed"
        result = SyncResult(error_code="OUTBOX_WRITE_FAILED", error_message="Unable to persist run_started event")
        try:
            self._outbox.persist({
                "schema_version": "1.0",
                "event_type": "run_started",
                "run_id": context.run_id,
                "correlation_id": context.correlation_id,
                "sync_code": context.sync_code,
                "occurred_at": started.isoformat(),
                "payload": {"trigger": context.trigger},
            })
            try:
                result = self._registry.resolve(context.sync_code).run(context)
                status = "success"
            except SyncInterrupted:
                status = "interrupted"
                result = SyncResult()
            except SyncNotFound:
                result = SyncResult(error_code="SYNC_NOT_FOUND", error_message="Synchronizer not registered")
            except Exception as exc:  # Synchronizer failures must not kill the control loop.
                error_code, error_message = self._diagnostic_error(exc)
                result = SyncResult(
                    error_code=error_code,
                    error_message=error_message,
                )
        except (OSError, TypeError, ValueError) as exc:
            result = SyncResult(error_code="OUTBOX_WRITE_FAILED", error_message=str(exc))
        finally:
            finished = datetime.now(UTC)
            duration_ms = int((finished - started).total_seconds() * 1000)
            self._record_local_result(context.sync_code, context.run_id, result, duration_ms, status)
            try:
                self._outbox.persist({
                    "schema_version": "1.0",
                    "event_type": "run_finished",
                    "run_id": context.run_id,
                    "correlation_id": context.correlation_id,
                    "sync_code": context.sync_code,
                    "occurred_at": finished.isoformat(),
                    "payload": result.as_payload(duration_ms, status, context.trigger),
                })
            except (OSError, TypeError, ValueError) as exc:
                # Disk loss must not leave this run permanently active in memory.
                result = SyncResult(error_code="OUTBOX_WRITE_FAILED", error_message=str(exc))
            finally:
                if self._run_state is not None:
                    self._run_state.mark_finished(context.run_id)
                with self._lock:
                    self._active.pop(context.run_id, None)
        return result

    def _record_local_result(
        self, sync_code: str, run_id: str, result: SyncResult, duration_ms: int, status: str
    ) -> None:
        if self._local_log is None or status == "interrupted":
            return
        try:
            if status == "success":
                self._local_log.record_success(sync_code, run_id, result, duration_ms)
            else:
                self._local_log.record_error(sync_code, run_id, result, duration_ms)
        except Exception:
            # The local BAPPS log is an operational aid; the outbox remains authoritative.
            pass

    @classmethod
    def _diagnostic_error(cls, exc: Exception) -> tuple[str, str]:
        """Keep the actionable exception while never exporting connection secrets."""
        raw_message = str(exc).strip() or "La excepción no entregó un mensaje."
        redacted = cls._URL_CREDENTIALS.sub(r"\1<redacted>\3", raw_message)
        redacted = cls._SECRET_VALUE.sub(r"\1\2<redacted>", redacted)
        redacted = redacted.replace("\x00", " ")[: cls._MAX_ERROR_DETAIL]
        prefixed = cls._CODE_PREFIX.fullmatch(redacted)
        if prefixed is not None:
            return prefixed.group(1), f"{type(exc).__name__}: {prefixed.group(2)}"
        if isinstance(exc, RecipeValidationError):
            return "INVALID_CONFIG", f"{type(exc).__name__}: {redacted}"
        return "UNEXPECTED_SYNC_ERROR", f"{type(exc).__name__}: {redacted}"
