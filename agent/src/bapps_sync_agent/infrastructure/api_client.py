import json
import platform
import socket
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bapps_sync_agent import __version__

from .config_store import AgentIdentity


class CentralApiUnavailable(RuntimeError):
    pass


class CentralApiError(RuntimeError):
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        super().__init__(str(body.get("error", {}).get("message", "Central API error")))
        self.status = status
        self.body = body


class ApiClient:
    def __init__(
        self,
        identity: AgentIdentity,
        timeout_seconds: float = 15.0,
        agent_version: str = __version__,
        machine_name: str | None = None,
    ) -> None:
        self._identity = identity
        self._timeout_seconds = timeout_seconds
        self._agent_version = agent_version
        self._machine_name = machine_name or platform.node() or socket.gethostname()

    def heartbeat(
        self,
        config_version: int,
        running_runs: list[dict[str, str]],
        outbox_pending: int,
        outbox_bytes: int,
    ) -> dict[str, Any]:
        return self._request("POST", "/api/v1/agent/heartbeat", {
            "schema_version": "1.0",
            "agent_code": self._identity.agent_code,
            "agent_version": self._agent_version,
            "config_version": config_version,
            "machine_name": self._machine_name,
            "status": "online",
            "running_runs": running_runs,
            "outbox": {"pending_count": outbox_pending, "pending_bytes": outbox_bytes},
        })

    def config(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/agent/config")

    def claim_commands(self, known_command_ids: list[str]) -> list[dict[str, Any]]:
        response = self._request("POST", "/api/v1/agent/commands/claim", {
            "agent_code": self._identity.agent_code,
            "max_commands": 5,
            "known_command_ids": known_command_ids,
        })
        return list(response.get("data", []))

    def complete_command(self, command_id: str, status: str, result: dict[str, object]) -> None:
        self._request("POST", f"/api/v1/agent/commands/{command_id}/result", {
            "status": status,
            "completed_at": datetime.now(UTC).isoformat(),
            "result": result,
        })

    def send_event(self, event: dict[str, object]) -> None:
        payload = dict(event)
        payload["agent_code"] = self._identity.agent_code
        self._request("POST", "/api/v1/agent/events", payload)

    def _request(self, method: str, path: str, payload: dict[str, object] | None = None) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(
            f"{self._identity.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._identity.agent_token}",
                "X-Agent-Code": self._identity.agent_code,
            },
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raw = exc.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except json.JSONDecodeError:
                body = {}
            if exc.code == 429 or exc.code >= 500:
                raise CentralApiUnavailable(f"Central API returned HTTP {exc.code}") from exc
            raise CentralApiError(exc.code, body) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise CentralApiUnavailable(str(exc)) from exc
