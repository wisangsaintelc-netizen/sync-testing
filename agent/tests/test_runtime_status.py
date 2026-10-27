import tempfile
import unittest
from pathlib import Path

from bapps_sync_agent.infrastructure.runtime_status_store import RuntimeStatusStore


class RuntimeStatusStoreTest(unittest.TestCase):
    def test_status_survives_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeStatusStore(Path(temporary))
            store.mark_online(7)

            status = RuntimeStatusStore(Path(temporary)).load()

            self.assertEqual(status.state, "online")
            self.assertEqual(status.config_version, 7)
            self.assertIsNone(status.last_heartbeat_at)

    def test_heartbeat_does_not_clear_a_configuration_security_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeStatusStore(Path(temporary))
            store.mark_heartbeat_online(6)
            store.mark_config_error("La firma de configuración no es válida.")
            store.mark_heartbeat_online(6)

            status = store.load()

            self.assertEqual(status.state, "degraded")
            self.assertEqual(status.config_error, "La firma de configuración no es válida.")
            self.assertIn("firma", status.message)
            self.assertIsNotNone(status.last_heartbeat_at)

    def test_valid_configuration_clears_the_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RuntimeStatusStore(Path(temporary))
            store.mark_heartbeat_online(6)
            store.mark_config_error("Firma inválida")
            store.mark_online(7)

            status = store.load()

            self.assertEqual(status.state, "online")
            self.assertIsNone(status.config_error)
            self.assertEqual(status.config_version, 7)
