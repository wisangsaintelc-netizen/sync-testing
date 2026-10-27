from typing import Callable

from bapps_sync_agent.application.sync_runner import SyncRunner
from bapps_sync_agent.domain.enums import CommandType
from bapps_sync_agent.domain.errors import SyncPaused
from bapps_sync_agent.infrastructure.command_journal import CommandJournal


class CommandHandler:
    def __init__(
        self,
        runner: SyncRunner,
        journal: CommandJournal,
        refresh_config: Callable[[], bool],
        set_sync_status: Callable[[str, str], None],
        inspect_source_table: Callable[[dict[str, object]], dict[str, object]] | None = None,
    ) -> None:
        self._runner = runner
        self._journal = journal
        self._refresh_config = refresh_config
        self._set_sync_status = set_sync_status
        self._inspect_source_table = inspect_source_table

    def handle(self, command: dict[str, object]) -> tuple[str, dict[str, object]]:
        command_id = str(command.get("command_id", ""))
        if not command_id:
            return "failed", {"error_code": "INVALID_COMMAND", "message": "Missing command_id"}
        known = self._journal.get(command_id)
        if known is not None:
            return str(known["status"]), dict(known.get("result", {}))

        try:
            command_type = CommandType(str(command["type"]))
            raw_payload = command.get("payload", {})
            if not isinstance(raw_payload, dict):
                raise ValueError("payload must be an object")
            payload = raw_payload
            if command_type is CommandType.RUN_NOW:
                if not self._refresh_config():
                    raise RuntimeError(
                        "CONFIG_REFRESH_FAILED: no se pudo descargar y validar la configuración actual antes de ejecutar."
                    )
                requested_run_id = payload.get("run_id")
                if requested_run_id is not None and (not isinstance(requested_run_id, str) or not requested_run_id):
                    raise ValueError("Invalid run_id")
                run_id, _future = self._runner.submit(
                    self._required(payload, "sync_code"), "command", requested_run_id
                )
                result = {"run_id": run_id}
                status = "completed"
            elif command_type is CommandType.STOP_RUN:
                stopped = self._runner.request_stop(self._required(payload, "run_id"))
                result = {} if stopped else {"skipped": "RUN_NOT_ACTIVE"}
                status = "completed" if stopped else "skipped"
            elif command_type is CommandType.PAUSE_SYNC:
                self._set_sync_status(self._required(payload, "sync_code"), "paused")
                status, result = "completed", {}
            elif command_type is CommandType.RESUME_SYNC:
                self._set_sync_status(self._required(payload, "sync_code"), "enabled")
                status, result = "completed", {}
            elif command_type is CommandType.INSPECT_SOURCE_TABLE:
                if self._inspect_source_table is None:
                    raise RuntimeError("SOURCE_INSPECTION_UNAVAILABLE")
                result = self._inspect_source_table(payload)
                status = "completed"
            else:
                if not self._refresh_config():
                    raise RuntimeError("CONFIG_REFRESH_FAILED: no se pudo descargar y validar la configuración actual.")
                status, result = "completed", {}
        except SyncPaused:
            status, result = "failed", {"error_code": "SYNC_PAUSED"}
        except RuntimeError as exc:
            message = str(exc)
            code, separator, detail = message.partition(":")
            status, result = "failed", {"error_code": code[:128]}
            if separator and detail.strip():
                result["message"] = detail.strip()[:1000]
        except (KeyError, TypeError, ValueError) as exc:
            status, result = "failed", {"error_code": "INVALID_COMMAND", "message": str(exc)}

        self._journal.record(command_id, status, result)
        return status, result

    @staticmethod
    def _required(payload: dict[str, object], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"Missing or invalid {key}")
        return value
