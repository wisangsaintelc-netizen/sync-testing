import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from bapps_sync_agent import __version__
from bapps_sync_agent.infrastructure.bootstrap_store import AgentBootstrap, BootstrapError, BootstrapStore
from bapps_sync_agent.infrastructure.enrollment_client import EnrollmentClient


class BootstrapTest(unittest.TestCase):
    def test_loads_valid_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bootstrap.json"
            path.write_text(json.dumps({
                "schema_version": "1.0",
                "base_url": "https://center.test/",
                "agent_code": "AGT-1",
                "enrollment_token": "0123456789abcdef",
            }), encoding="utf-8")

            bootstrap = BootstrapStore(path).load()

            self.assertEqual(bootstrap.base_url, "https://center.test")
            self.assertEqual(bootstrap.agent_code, "AGT-1")

    def test_rejects_bootstrap_with_short_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bootstrap.json"
            path.write_text(json.dumps({
                "schema_version": "1.0",
                "base_url": "https://center.test",
                "agent_code": "AGT-1",
                "enrollment_token": "short",
            }), encoding="utf-8")

            with self.assertRaises(BootstrapError):
                BootstrapStore(path).load()

    @patch("bapps_sync_agent.infrastructure.enrollment_client.urlopen")
    def test_enrollment_client_saves_only_center_identity(self, urlopen: MagicMock) -> None:
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b'{"agent_code":"AGT-1","agent_token":"agent-token","config_version":1}'
        identity = EnrollmentClient().enroll(AgentBootstrap(
            base_url="https://center.test",
            agent_code="AGT-1",
            enrollment_token="0123456789abcdef",
        ))

        self.assertEqual(identity.agent_code, "AGT-1")
        self.assertEqual(identity.agent_token, "agent-token")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://center.test/api/v1/agent/enroll")
        self.assertNotIn(b"agent-token", request.data)
        self.assertEqual(json.loads(request.data)["agent_version"], __version__)
