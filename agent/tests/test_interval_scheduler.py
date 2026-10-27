import unittest

from bapps_sync_agent.application.interval_scheduler import IntervalScheduler


class IntervalSchedulerTest(unittest.TestCase):
    def test_first_execution_waits_for_interval_then_repeats(self) -> None:
        scheduler = IntervalScheduler()
        config = {"syncs": [{"code": "clientes_valery", "status": "enabled", "interval_seconds": 900}]}

        self.assertEqual(scheduler.due_sync_codes(config, now=100.0), [])
        self.assertEqual(scheduler.due_sync_codes(config, now=999.0), [])
        self.assertEqual(scheduler.due_sync_codes(config, now=1000.0), ["clientes_valery"])
        self.assertEqual(scheduler.due_sync_codes(config, now=1900.0), ["clientes_valery"])

    def test_pause_or_interval_change_resets_the_plan(self) -> None:
        scheduler = IntervalScheduler()
        enabled = {"syncs": [{"code": "clientes_valery", "status": "enabled", "interval_seconds": 900}]}
        scheduler.due_sync_codes(enabled, now=0.0)
        self.assertEqual(scheduler.due_sync_codes({"syncs": [{"code": "clientes_valery", "status": "paused", "interval_seconds": 900}]}, now=900.0), [])
        changed = {"syncs": [{"code": "clientes_valery", "status": "enabled", "interval_seconds": 1200}]}
        self.assertEqual(scheduler.due_sync_codes(changed, now=900.0), [])
        self.assertEqual(scheduler.due_sync_codes(changed, now=2100.0), ["clientes_valery"])
