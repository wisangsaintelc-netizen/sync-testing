import tempfile
import unittest
from pathlib import Path

from bapps_sync_agent.application.agent_service import AgentService
from bapps_sync_agent.infrastructure.command_journal import CommandJournal
from bapps_sync_agent.infrastructure.config_store import AgentIdentity, ConfigStore
from bapps_sync_agent.infrastructure.api_client import CentralApiUnavailable
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.infrastructure.run_state_store import RunStateStore


class FakeRunner:
    def __init__(self) -> None:
        self.submissions: list[tuple[str, str]] = []

    def active_runs(self) -> list[dict[str, str]]:
        return []

    def submit(self, sync_code: str, trigger: str):
        self.submissions.append((sync_code, trigger))


class RecordingApiClient:
    def __init__(self) -> None:
        self.sent_events: list[dict[str, object]] = []

    def send_event(self, event: dict[str, object]) -> None:
        self.sent_events.append(event)


class UnavailableApiClient:
    def heartbeat(self, **_kwargs):
        raise CentralApiUnavailable("Centro fuera de línea")

    def send_event(self, _event: dict[str, object]) -> None:
        raise CentralApiUnavailable("Centro fuera de línea")


class RecipeApiClient:
    def config(self):
        return {
            "agent_code": "AGT-PROFIT-01",
            "syncs": [{"code": "profit_factura", "config": {"recipe": {"engine": "declarative_table_reader"}}}],
        }


class DowngradedConfigApiClient:
    def config(self):
        return {"version": 4, "agent_code": "AGT-PROFIT-01", "syncs": []}


class AllowConfigSignatureVerifier:
    def verify(self, _config, _identity):
        pass


class RecordingRuntimeStatus:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def mark_error(self, message: str) -> None:
        self.errors.append(message)

    def mark_config_error(self, message: str) -> None:
        self.errors.append(message)

    def mark_heartbeat_online(self, _version: int) -> None:
        pass

    def mark_online(self, _version: int) -> None:
        pass


class AgentServiceOutboxTest(unittest.TestCase):
    def test_failed_config_refresh_uses_exponential_backoff_without_heartbeat_reset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_store = ConfigStore(root)
            config_store.save_identity(AgentIdentity("AGT-PROFIT-01", "token", "https://center.test"))
            service = AgentService(
                root=root,
                api_client=RecipeApiClient(),
                config_store=config_store,
                outbox=Outbox(root),
                runner=FakeRunner(),
                journal=CommandJournal(root),
                random_source=__import__("random").Random(0),
            )

            self.assertFalse(service._refresh_config(now=100.0))
            first_retry = service._next_config_refresh_at
            self.assertGreaterEqual(first_retry, 105.0)

            service.request_config_refresh()
            self.assertEqual(service._next_config_refresh_at, first_retry)

            self.assertFalse(service._refresh_config(now=first_retry))
            self.assertGreaterEqual(service._next_config_refresh_at, first_retry + 10.0)

    def test_corrupt_event_is_quarantined_without_blocking_later_valid_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outbox = Outbox(root)
            corrupt = root / "outbox" / "pending" / "EVT-000-corrupt.json"
            corrupt.write_text("{not valid json", encoding="utf-8")
            outbox.persist({"event_id": "EVT-999-valid", "event_type": "run_finished"})
            api_client = RecordingApiClient()
            service = AgentService(
                root=root,
                api_client=api_client,
                config_store=ConfigStore(root),
                outbox=outbox,
                runner=FakeRunner(),
                journal=CommandJournal(root),
            )

            service._flush_outbox()

            self.assertTrue((root / "outbox" / "failed" / corrupt.name).exists())
            self.assertEqual(api_client.sent_events, [{"event_id": "EVT-999-valid", "event_type": "run_finished"}])
            self.assertEqual(outbox.pending(), [])
            self.assertEqual(outbox.backlog_stats(), (0, 0))

    def test_restart_emits_interrupted_event_for_an_unfinished_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_state = RunStateStore(root)
            run_state.mark_started({
                "run_id": "RUN-INTERRUPTED",
                "correlation_id": "CORR-INTERRUPTED",
                "sync_code": "clientes_valery",
                "trigger": "schedule",
                "started_at": "2026-07-23T16:00:00+00:00",
            })
            outbox = Outbox(root)
            service = AgentService(
                root=root,
                api_client=RecordingApiClient(),
                config_store=ConfigStore(root),
                outbox=outbox,
                runner=FakeRunner(),
                journal=CommandJournal(root),
                run_state=run_state,
            )

            service._emit_startup_events()

            events = [Outbox.read(path) for path in outbox.pending()]
            interrupted = next(event for event in events if event["event_type"] == "run_finished")
            self.assertEqual(interrupted["run_id"], "RUN-INTERRUPTED")
            self.assertEqual(interrupted["payload"]["status"], "interrupted")
            self.assertEqual(interrupted["payload"]["error_code"], "AGENT_RESTARTED")
            self.assertEqual(run_state.recover_interrupted(), [])

    def test_central_outage_keeps_events_durable_and_does_not_stop_scheduling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_store = ConfigStore(root)
            config_store.save_active_config({
                "version": 3,
                "syncs": [{"code": "clientes_valery", "status": "enabled", "interval_seconds": 60}],
            })
            outbox = Outbox(root)
            outbox.persist({"event_id": "EVT-CENTRAL-OFFLINE", "event_type": "run_finished"})
            runner = FakeRunner()
            service = AgentService(
                root=root,
                api_client=UnavailableApiClient(),
                config_store=config_store,
                outbox=outbox,
                runner=runner,
                journal=CommandJournal(root),
            )

            service._flush_outbox()
            service._heartbeat()
            service._schedule_due_syncs(0.0)
            service._schedule_due_syncs(60.0)

            self.assertTrue((root / "outbox" / "pending" / "EVT-CENTRAL-OFFLINE.json").exists())
            self.assertEqual(runner.submissions, [("clientes_valery", "schedule")])

    def test_unsigned_recipe_config_is_not_saved_or_activated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_store = ConfigStore(root)
            config_store.save_identity(AgentIdentity("AGT-PROFIT-01", "token", "https://center.test"))
            status = RecordingRuntimeStatus()
            service = AgentService(
                root=root,
                api_client=RecipeApiClient(),
                config_store=config_store,
                outbox=Outbox(root),
                runner=FakeRunner(),
                journal=CommandJournal(root),
                runtime_status=status,
            )

            service._refresh_config()

            self.assertIsNone(config_store.load_active_config())
            self.assertTrue(any("firmada" in error for error in status.errors))

    def test_an_older_configuration_version_is_never_activated_silently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_store = ConfigStore(root)
            config_store.save_active_config({"version": 5, "syncs": []})
            status = RecordingRuntimeStatus()
            service = AgentService(
                root=root,
                api_client=DowngradedConfigApiClient(),
                config_store=config_store,
                outbox=Outbox(root),
                runner=FakeRunner(),
                journal=CommandJournal(root),
                runtime_status=status,
                config_signature_verifier=AllowConfigSignatureVerifier(),
            )

            service._refresh_config()

            self.assertEqual(config_store.load_active_config()["version"], 5)
            self.assertTrue(any("CONFIG_ROLLBACK_REJECTED" in error for error in status.errors))
