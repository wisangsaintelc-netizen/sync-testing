import json
import tempfile
import unittest
from pathlib import Path
from threading import Event

from bapps_sync_agent.application.sync_runner import SyncRunner
from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.syncs.registry import SynchronizerRegistry


class SuccessfulSynchronizer:
    def run(self, context):
        context.raise_if_stopped()
        return SyncResult(rows_read=12, rows_inserted=10, rows_updated=2)


class StoppingSynchronizer:
    def run(self, context):
        context.stop_event.wait(timeout=2)
        context.raise_if_stopped()
        return SyncResult()


class FailingSynchronizer:
    def run(self, _context):
        raise RuntimeError("origen no disponible")


class SecretFailingSynchronizer:
    def run(self, _context):
        raise RuntimeError("mysql://sync:target-secret@mysql.test/bapps?token=agent-token")


class BlockingSynchronizer:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls = 0

    def run(self, context):
        self.calls += 1
        self.started.set()
        self.release.wait(timeout=2)
        context.raise_if_stopped()
        return SyncResult()


class CountingSynchronizer:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, _context):
        self.calls += 1
        return SyncResult()


class UnwritableOutbox:
    def persist(self, _event) -> str:
        raise OSError("Disk full")


class CapturingLocalLog:
    def __init__(self, fail=False):
        self.successes = []
        self.errors = []
        self.fail = fail

    def record_success(self, *args):
        self.successes.append(args)
        if self.fail:
            raise RuntimeError("log local no disponible")

    def record_error(self, *args):
        self.errors.append(args)
        if self.fail:
            raise RuntimeError("log local no disponible")


class SyncRunnerTest(unittest.TestCase):
    def test_runner_persists_started_and_finished_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary))
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": SuccessfulSynchronizer()}),
                outbox,
                is_enabled=lambda _code: True,
            )
            run_id, future = runner.submit("clientes_valery", "command")
            result = future.result(timeout=2)
            runner.shutdown()

            self.assertEqual(result.rows_read, 12)
            events = [Outbox.read(path) for path in outbox.pending()]
            self.assertEqual({event["event_type"] for event in events}, {"run_started", "run_finished"})
            self.assertEqual({event["run_id"] for event in events}, {run_id})

    def test_runner_honors_a_preassigned_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary))
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": SuccessfulSynchronizer()}),
                outbox,
                is_enabled=lambda _code: True,
            )
            run_id, future = runner.submit("clientes_valery", "command", "RUN-RETRY-1")
            future.result(timeout=2)
            runner.shutdown()

            events = [Outbox.read(path) for path in outbox.pending()]
            self.assertEqual(run_id, "RUN-RETRY-1")
            self.assertEqual({event["run_id"] for event in events}, {"RUN-RETRY-1"})

    def test_stop_is_cooperative_and_creates_interrupted_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary))
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": StoppingSynchronizer()}),
                outbox,
                is_enabled=lambda _code: True,
            )
            run_id, future = runner.submit("clientes_valery", "command")
            self.assertTrue(runner.request_stop(run_id))
            future.result(timeout=2)
            runner.shutdown()

            finished = next(event for event in (Outbox.read(path) for path in outbox.pending()) if event["event_type"] == "run_finished")
            self.assertEqual(finished["payload"]["status"], "interrupted")

    def test_schedule_and_manual_run_cannot_execute_the_same_sync_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            synchronizer = BlockingSynchronizer()
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": synchronizer}),
                Outbox(Path(temporary)),
                is_enabled=lambda _code: True,
            )
            _, scheduled = runner.submit("clientes_valery", "schedule")
            self.assertTrue(synchronizer.started.wait(timeout=1))

            with self.assertRaisesRegex(RuntimeError, "SYNC_ALREADY_RUNNING"):
                runner.submit("clientes_valery", "command")

            synchronizer.release.set()
            scheduled.result(timeout=2)
            runner.shutdown()

    def test_two_manual_run_now_commands_cannot_execute_the_same_sync_twice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            synchronizer = BlockingSynchronizer()
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": synchronizer}),
                Outbox(Path(temporary)),
                is_enabled=lambda _code: True,
            )
            _, first = runner.submit("clientes_valery", "command")
            self.assertTrue(synchronizer.started.wait(timeout=1))

            with self.assertRaisesRegex(RuntimeError, "SYNC_ALREADY_RUNNING"):
                runner.submit("clientes_valery", "command")

            synchronizer.release.set()
            first.result(timeout=2)
            runner.shutdown()

            self.assertEqual(synchronizer.calls, 1)

    def test_stop_racing_with_completion_emits_one_terminal_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            synchronizer = BlockingSynchronizer()
            outbox = Outbox(Path(temporary))
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": synchronizer}),
                outbox,
                is_enabled=lambda _code: True,
            )
            run_id, future = runner.submit("clientes_valery", "command")
            self.assertTrue(synchronizer.started.wait(timeout=1))

            self.assertTrue(runner.request_stop(run_id))
            synchronizer.release.set()
            future.result(timeout=2)
            runner.shutdown()

            finished = [
                event for event in (Outbox.read(path) for path in outbox.pending())
                if event["event_type"] == "run_finished" and event["run_id"] == run_id
            ]
            self.assertEqual(len(finished), 1)
            self.assertEqual(finished[0]["payload"]["status"], "interrupted")
            self.assertEqual(runner.active_runs(), [])

    def test_unwritable_outbox_blocks_the_sync_before_touching_the_source(self) -> None:
        synchronizer = CountingSynchronizer()
        runner = SyncRunner(
            SynchronizerRegistry({"clientes_valery": synchronizer}),
            UnwritableOutbox(),
            is_enabled=lambda _code: True,
        )

        _, future = runner.submit("clientes_valery", "command")
        result = future.result(timeout=2)
        runner.shutdown()

        self.assertEqual(result.error_code, "OUTBOX_WRITE_FAILED")
        self.assertEqual(synchronizer.calls, 0)
        self.assertEqual(runner.active_runs(), [])

    def test_runner_records_success_locally_without_changing_the_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = CapturingLocalLog()
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": SuccessfulSynchronizer()}),
                Outbox(Path(temporary)), is_enabled=lambda _code: True, local_log=log,
            )
            run_id, future = runner.submit("clientes_valery", "command")
            result = future.result(timeout=2)
            runner.shutdown()

            self.assertIsNone(result.error_code)
            self.assertEqual(log.successes[0][1], run_id)
            self.assertEqual(log.errors, [])

    def test_runner_keeps_the_sync_result_when_local_logging_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = CapturingLocalLog(fail=True)
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": SuccessfulSynchronizer()}),
                Outbox(Path(temporary)), is_enabled=lambda _code: True, local_log=log,
            )
            _, future = runner.submit("clientes_valery", "command")
            result = future.result(timeout=2)
            runner.shutdown()

            self.assertEqual(result.rows_read, 12)
            self.assertIsNone(result.error_code)

    def test_runner_records_a_failed_sync_locally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log = CapturingLocalLog()
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": FailingSynchronizer()}),
                Outbox(Path(temporary)), is_enabled=lambda _code: True, local_log=log,
            )
            run_id, future = runner.submit("clientes_valery", "command")
            result = future.result(timeout=2)
            runner.shutdown()

            self.assertEqual(result.error_code, "UNEXPECTED_SYNC_ERROR")
            self.assertIn("RuntimeError: origen no disponible", result.error_message or "")
            self.assertEqual(log.errors[0][1], run_id)

    def test_unexpected_sync_errors_do_not_persist_driver_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary))
            runner = SyncRunner(
                SynchronizerRegistry({"clientes_valery": SecretFailingSynchronizer()}),
                outbox,
                is_enabled=lambda _code: True,
            )
            _, future = runner.submit("clientes_valery", "command")
            result = future.result(timeout=2)
            runner.shutdown()

            self.assertEqual(result.error_code, "UNEXPECTED_SYNC_ERROR")
            self.assertNotIn("target-secret", result.error_message or "")
            self.assertNotIn("agent-token", result.error_message or "")
            serialized_events = "\n".join(
                json.dumps(Outbox.read(path)) for path in outbox.pending()
            )
            self.assertNotIn("target-secret", serialized_events)
            self.assertNotIn("agent-token", serialized_events)
            self.assertIn("RuntimeError:", result.error_message or "")
