import tempfile
import unittest
from pathlib import Path

from bapps_sync_agent.application.command_handler import CommandHandler
from bapps_sync_agent.infrastructure.command_journal import CommandJournal


class FakeRunner:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str, str | None]] = []
        self.stop_requests: list[str] = []
        self.stop_result = True

    def submit(self, sync_code: str, trigger: str, run_id: str | None = None):
        self.submissions.append((sync_code, trigger, run_id))
        return run_id or "RUN-COMMAND-1", object()

    def request_stop(self, run_id: str) -> bool:
        self.stop_requests.append(run_id)
        return self.stop_result


class CommandHandlerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.runner = FakeRunner()
        self.status_changes: list[tuple[str, str]] = []
        self.inspections: list[dict[str, object]] = []
        self.refreshes = 0

        self.refresh_result = True

        def refresh() -> bool:
            self.refreshes += 1
            return self.refresh_result

        self.handler = CommandHandler(
            self.runner,
            CommandJournal(Path(self.temporary.name)),
            refresh_config=refresh,
            set_sync_status=lambda code, status: self.status_changes.append((code, status)),
            inspect_source_table=lambda payload: self._inspect(payload),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _inspect(self, payload: dict[str, object]) -> dict[str, object]:
        self.inspections.append(payload)
        return {"table": str(payload["table"]), "columns": [{"name": "CODIGO", "type": "str", "sample": "V01"}]}

    def test_run_now_is_idempotent_by_command_id(self) -> None:
        command = {"command_id": "CMD-1", "type": "run_now", "payload": {"sync_code": "clientes_valery"}}

        first = self.handler.handle(command)
        duplicate = self.handler.handle(command)

        self.assertEqual(first, ("completed", {"run_id": "RUN-COMMAND-1"}))
        self.assertEqual(duplicate, first)
        self.assertEqual(self.runner.submissions, [("clientes_valery", "command", None)])
        self.assertEqual(self.refreshes, 1)

    def test_run_now_requires_the_latest_valid_configuration(self) -> None:
        self.refresh_result = False

        result = self.handler.handle({
            "command_id": "CMD-CONFIG", "type": "run_now", "payload": {"sync_code": "clientes_valery"},
        })

        self.assertEqual(result[0], "failed")
        self.assertEqual(result[1]["error_code"], "CONFIG_REFRESH_FAILED")
        self.assertEqual(self.runner.submissions, [])

    def test_run_now_honors_the_run_id_preassigned_by_the_control_center(self) -> None:
        result = self.handler.handle({
            "command_id": "CMD-RETRY", "type": "run_now",
            "payload": {"sync_code": "clientes_valery", "run_id": "RUN-RETRY-1"},
        })

        self.assertEqual(result, ("completed", {"run_id": "RUN-RETRY-1"}))
        self.assertEqual(self.runner.submissions, [("clientes_valery", "command", "RUN-RETRY-1")])

    def test_stop_run_reports_completed_or_skipped(self) -> None:
        completed = self.handler.handle({"command_id": "CMD-STOP-1", "type": "stop_run", "payload": {"run_id": "RUN-1"}})
        self.runner.stop_result = False
        skipped = self.handler.handle({"command_id": "CMD-STOP-2", "type": "stop_run", "payload": {"run_id": "RUN-2"}})

        self.assertEqual(completed, ("completed", {}))
        self.assertEqual(skipped, ("skipped", {"skipped": "RUN_NOT_ACTIVE"}))
        self.assertEqual(self.runner.stop_requests, ["RUN-1", "RUN-2"])

    def test_pause_resume_and_refresh_config_dispatch_their_intended_action(self) -> None:
        paused = self.handler.handle({"command_id": "CMD-PAUSE", "type": "pause_sync", "payload": {"sync_code": "clientes_valery"}})
        resumed = self.handler.handle({"command_id": "CMD-RESUME", "type": "resume_sync", "payload": {"sync_code": "clientes_valery"}})
        refreshed = self.handler.handle({"command_id": "CMD-REFRESH", "type": "refresh_config", "payload": {}})

        self.assertEqual(paused, ("completed", {}))
        self.assertEqual(resumed, ("completed", {}))
        self.assertEqual(refreshed, ("completed", {}))
        self.assertEqual(self.status_changes, [("clientes_valery", "paused"), ("clientes_valery", "enabled")])
        self.assertEqual(self.refreshes, 1)

    def test_invalid_payload_is_recorded_as_failed_and_not_retried(self) -> None:
        command = {"command_id": "CMD-BAD", "type": "run_now", "payload": {}}

        first = self.handler.handle(command)
        duplicate = self.handler.handle(command)

        self.assertEqual(first[0], "failed")
        self.assertEqual(first[1]["error_code"], "INVALID_COMMAND")
        self.assertEqual(duplicate, first)
        self.assertEqual(self.runner.submissions, [])

    def test_source_inspection_dispatches_the_limited_payload_and_is_idempotent(self) -> None:
        command = {
            "command_id": "CMD-INSPECT",
            "type": "inspect_source_table",
            "payload": {
                "profile_ref": "default",
                "driver": "firebird",
                "table": "VENDEDORES",
                "position": 4,
            },
        }

        first = self.handler.handle(command)
        duplicate = self.handler.handle(command)

        self.assertEqual(first[0], "completed")
        self.assertEqual(first[1]["table"], "VENDEDORES")
        self.assertEqual(self.inspections[0]["position"], 4)
        self.assertEqual(duplicate, first)
        self.assertEqual(len(self.inspections), 1)
