import json
import platform
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from bapps_sync_agent import __version__

from .bootstrap_store import AgentBootstrap
from .config_store import AgentIdentity


class EnrollmentError(RuntimeError):
    pass


class EnrollmentClient:
    def __init__(self, timeout_seconds: float = 15.0, agent_version: str = __version__) -> None:
        self._timeout_seconds = timeout_seconds
        self._agent_version = agent_version

    def enroll(self, bootstrap: AgentBootstrap) -> AgentIdentity:
        payload = {
            "agent_code": bootstrap.agent_code,
            "enrollment_token": bootstrap.enrollment_token,
            "machine_name": platform.node() or socket.gethostname(),
            "agent_version": self._agent_version,
            "os": platform.platform(),
        }
        request = Request(
            f"{bootstrap.base_url}/api/v1/agent/enroll",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = self._read_error(exc)
            message = body.get("message") or "El Centro BAPPS rechazó el enrolamiento."
            raise EnrollmentError(str(message)) from exc
        except (URLError, TimeoutError, socket.timeout) as exc:
            raise EnrollmentError(f"No se pudo contactar el Centro BAPPS: {exc}") from exc

        agent_code = body.get("agent_code")
        agent_token = body.get("agent_token")
        if not isinstance(agent_code, str) or not isinstance(agent_token, str) or not agent_token:
            raise EnrollmentError("El Centro BAPPS devolvió una respuesta de enrolamiento inválida.")
        if agent_code != bootstrap.agent_code:
            raise EnrollmentError("El Centro BAPPS devolvió la identidad de otro agente.")
        public_key = body.get("config_signing_public_key")
        key_id = body.get("config_signing_key_id")
        if public_key is not None and (not isinstance(public_key, str) or not public_key):
            raise EnrollmentError("La clave pública de firma recibida es inválida.")
        if key_id is not None and (not isinstance(key_id, str) or not key_id):
            raise EnrollmentError("El identificador de clave de firma recibido es inválido.")
        return AgentIdentity(
            agent_code=agent_code,
            agent_token=agent_token,
            base_url=bootstrap.base_url,
            config_signing_public_key=public_key,
            config_signing_key_id=key_id,
        )

    @staticmethod
    def _read_error(exc: HTTPError) -> dict[str, str]:
        try:
            raw = json.loads(exc.read().decode("utf-8"))
            error = raw.get("error", {}) if isinstance(raw, dict) else {}
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    return {"message": message}
            errors = raw.get("errors", {}) if isinstance(raw, dict) else {}
            if isinstance(errors, dict):
                first = next(iter(errors.values()), [])
                if isinstance(first, list) and first and isinstance(first[0], str):
                    return {"message": first[0]}
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return {}
