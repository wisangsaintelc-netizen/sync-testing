import json
import unittest
from unittest.mock import MagicMock, patch

from bapps_sync_agent import __version__
from bapps_sync_agent.infrastructure.api_client import ApiClient
from bapps_sync_agent.infrastructure.config_store import AgentIdentity


class ApiClientTest(unittest.TestCase):
    @patch("bapps_sync_agent.infrastructure.api_client.urlopen")
    def test_heartbeat_reports_the_package_version(self, urlopen: MagicMock) -> None:
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"{}"
        client = ApiClient(
            AgentIdentity("AGT-1", "agent-token", "https://center.test"),
            machine_name="TEST-HOST",
        )

        client.heartbeat(config_version=3, running_runs=[], outbox_pending=0, outbox_bytes=0)

        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(payload["agent_version"], __version__)
        self.assertEqual(payload["agent_code"], "AGT-1")
