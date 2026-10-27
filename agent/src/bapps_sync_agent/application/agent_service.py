from pathlib import Path
from datetime import UTC, datetime
from random import Random
from threading import Event
from time import monotonic
from typing import Callable

from bapps_sync_agent.application.command_handler import CommandHandler
from bapps_sync_agent.application.interval_scheduler import IntervalScheduler
from bapps_sync_agent.application.sync_runner import SyncRunner
from bapps_sync_agent.infrastructure.api_client import ApiClient, CentralApiError, CentralApiUnavailable
from bapps_sync_agent.domain.errors import SyncNotFound, SyncPaused
from bapps_sync_agent.infrastructure.command_journal import CommandJournal
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.config_signature import ConfigSignatureError, ConfigSignatureVerifier
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.infrastructure.run_state_store import RunStateStore
from bapps_sync_agent.infrastructure.runtime_status_store import RuntimeStatusStore
from bapps_sync_agent.infrastructure.single_instance_lock import SingleInstanceLock


class AgentService:
    def __init__(
        self,
        root: Path,
        api_client: ApiClient,
        config_store: ConfigStore,
        outbox: Outbox,
        runner: SyncRunner,
        journal: CommandJournal,
        run_state: RunStateStore | None = None,
        runtime_status: RuntimeStatusStore | None = None,
        config_signature_verifier: ConfigSignatureVerifier | None = None,
        inspect_source_table: Callable[[dict[str, object]], dict[str, object]] | None = None,
        heartbeat_interval_seconds: float = 30.0,
        command_poll_interval_seconds: float = 5.0,
        random_source: Random | None = None,
    ) -> None:
        self._root = root
        self._api_client = api_client
        self._config_store = config_store
        self._outbox = outbox
        self._runner = runner
        self._journal = journal
        self._run_state = run_state
        self._runtime_status = runtime_status
        self._config_signature_verifier = config_signature_verifier or ConfigSignatureVerifier()
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._command_poll_interval_seconds = command_poll_interval_seconds
        self._random = random_source or Random()
        self._stop_event = Event()
        self._force_config_refresh = True
        self._config_refresh_failures = 0
        self._next_config_refresh_at = 0.0
        self._scheduler = IntervalScheduler()
        self._command_handler = CommandHandler(
            runner=runner,
            journal=journal,
            refresh_config=self._refresh_config,
            set_sync_status=self._set_sync_status,
            inspect_source_table=inspect_source_table,
        )

    def request_config_refresh(self) -> None:
        if not self._force_config_refresh:
            self._next_config_refresh_at = 0.0
        self._force_config_refresh = True

    def run_forever(self) -> None:
        lock = SingleInstanceLock(self._root)
        lock.acquire()
        self._outbox.recover_sending()
        self._emit_startup_events()
        try:
            next_heartbeat = 0.0
            next_claim = 0.0
            while not self._stop_event.is_set():
                now = monotonic()
                self._flush_outbox()
                if self._force_config_refresh and now >= self._next_config_refresh_at:
                    self._refresh_config(now)
                if now >= next_heartbeat:
                    self._heartbeat()
                    next_heartbeat = self._next_due(now, self._heartbeat_interval_seconds)
                if now >= next_claim:
                    self._claim_commands()
                    next_claim = self._next_due(now, self._command_poll_interval_seconds)
                self._schedule_due_syncs(now)
                self._stop_event.wait(timeout=1)
        finally:
            self._runner.shutdown()
            lock.release()

    def stop(self) -> None:
        self._stop_event.set()

    def _heartbeat(self) -> None:
        config = self._config_store.load_active_config() or {"version": 0}
        pending_count, pending_bytes = self._outbox.backlog_stats()
        try:
            response = self._api_client.heartbeat(
                config_version=int(config.get("version", 0)),
                running_runs=self._runner.active_runs(),
                outbox_pending=pending_count,
                outbox_bytes=pending_bytes,
            )
        except (CentralApiUnavailable, CentralApiError):
            if self._runtime_status is not None:
                self._runtime_status.mark_error("No se pudo enviar el heartbeat al Centro BAPPS.")
            return
        if self._runtime_status is not None:
            self._runtime_status.mark_heartbeat_online(int(config.get("version", 0)))
        if response.get("latest_config_version") != config.get("version"):
            self.request_config_refresh()

    def _refresh_config(self, now: float | None = None) -> bool:
        attempted_at = monotonic() if now is None else now
        try:
            config = self._api_client.config()
            verified_by = self._config_signature_verifier.verify(
                config, self._config_store.load_identity()
            )
            trust_update = config.get("config_signing_trust_update")
            if trust_update is not None:
                if verified_by is None or not isinstance(trust_update, dict):
                    raise ConfigSignatureError("La transición del llavero no está firmada correctamente.")
                self._config_store.apply_signed_trust_update(trust_update, verified_by)
        except (ConfigSignatureError, ValueError) as exc:
            if self._runtime_status is not None:
                self._runtime_status.mark_config_error(str(exc))
            self._schedule_config_retry(attempted_at)
            return False
        except (CentralApiUnavailable, CentralApiError):
            if self._runtime_status is not None:
                self._runtime_status.mark_error("No se pudo descargar la configuración del Centro BAPPS.")
            self._schedule_config_retry(attempted_at)
            return False
        current = self._config_store.load_active_config() or {}
        current_version = current.get("version", 0)
        incoming_version = config.get("version")
        if (
            not isinstance(incoming_version, int)
            or isinstance(incoming_version, bool)
            or incoming_version < 0
        ):
            if self._runtime_status is not None:
                self._runtime_status.mark_config_error("La configuración del Centro no contiene una versión válida.")
            self._schedule_config_retry(attempted_at)
            return False
        if isinstance(current_version, int) and incoming_version < current_version:
            if self._runtime_status is not None:
                self._runtime_status.mark_config_error(
                    "CONFIG_ROLLBACK_REJECTED: el Centro intentó entregar una versión anterior."
                )
            self._schedule_config_retry(attempted_at)
            return False
        self._config_store.save_active_config(config)
        if self._runtime_status is not None:
            self._runtime_status.mark_online(int(config.get("version", 0)))
        self._force_config_refresh = False
        self._config_refresh_failures = 0
        self._next_config_refresh_at = 0.0
        return True

    def _schedule_config_retry(self, now: float) -> None:
        self._config_refresh_failures += 1
        base_seconds = min(300.0, 5.0 * (2 ** min(self._config_refresh_failures - 1, 6)))
        self._next_config_refresh_at = self._next_due(now, base_seconds)

    def _claim_commands(self) -> None:
        try:
            commands = self._api_client.claim_commands([])
        except (CentralApiUnavailable, CentralApiError):
            return
        for command in commands:
            status, result = self._command_handler.handle(command)
            try:
                self._api_client.complete_command(str(command["command_id"]), status, result)
            except (CentralApiUnavailable, CentralApiError):
                return

    def _schedule_due_syncs(self, now: float) -> None:
        config = self._config_store.load_active_config() or {}
        for sync_code in self._scheduler.due_sync_codes(config, now):
            try:
                self._runner.submit(sync_code, "schedule")
            except (SyncPaused, SyncNotFound, RuntimeError):
                # A command may already be running this sync, or its implementation may be unavailable.
                # The scheduler will try again at the next configured interval.
                continue

    def _flush_outbox(self) -> None:
        for pending in self._outbox.pending():
            sending = self._outbox.claim(pending)
            try:
                self._api_client.send_event(self._outbox.read(sending))
            except CentralApiUnavailable:
                self._outbox.retry(sending)
                return
            except CentralApiError:
                self._outbox.fail(sending)
            except (OSError, ValueError, TypeError, KeyError):
                self._outbox.fail(sending)
            else:
                self._outbox.acknowledge(sending)

    def _set_sync_status(self, sync_code: str, status: str) -> None:
        config = self._config_store.load_active_config()
        if config is None:
            return
        for sync in list(config.get("syncs", [])):
            if sync.get("code") == sync_code:
                sync["status"] = status
        self._config_store.save_active_config(config)

    def _emit_startup_events(self) -> None:
        self._outbox.persist({
            "schema_version": "1.0",
            "event_type": "agent_started",
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": {},
        })
        if self._run_state is None:
            return
        for run in self._run_state.recover_interrupted():
            self._outbox.persist({
                "schema_version": "1.0",
                "event_type": "run_finished",
                "run_id": run["run_id"],
                "correlation_id": run["correlation_id"],
                "sync_code": run["sync_code"],
                "occurred_at": datetime.now(UTC).isoformat(),
                "payload": {
                    "status": "interrupted",
                    "trigger": run.get("trigger", "schedule"),
                    "rows_read": 0,
                    "rows_inserted": 0,
                    "rows_updated": 0,
                    "rows_deleted": 0,
                    "rows_failed": 0,
                    "duration_ms": 0,
                    "error_code": "AGENT_RESTARTED",
                    "error_message": "The agent restarted before this run completed.",
                },
            })

    def _next_due(self, now: float, interval_seconds: float) -> float:
        # Small per-agent jitter avoids all agents polling simultaneously.
        return now + interval_seconds + self._random.uniform(0.0, min(1.0, interval_seconds * 0.1))
