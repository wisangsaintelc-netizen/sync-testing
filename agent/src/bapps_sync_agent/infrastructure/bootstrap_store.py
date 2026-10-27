import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .atomic_json import read_json


class BootstrapError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentBootstrap:
    base_url: str
    agent_code: str
    enrollment_token: str


class BootstrapStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent / "bootstrap.json"
        return Path.cwd() / "bootstrap.json"

    def load(self) -> AgentBootstrap | None:
        data = read_json(self._path, None)
        if data is None:
            return None
        if not isinstance(data, dict):
            raise BootstrapError("El archivo bootstrap.json debe contener un objeto JSON.")
        if data.get("schema_version") != "1.0":
            raise BootstrapError("La versión del bootstrap no es compatible.")

        base_url = str(data.get("base_url", "")).rstrip("/")
        agent_code = str(data.get("agent_code", "")).strip()
        enrollment_token = str(data.get("enrollment_token", ""))
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise BootstrapError("El bootstrap no contiene una URL válida del Centro BAPPS.")
        if not agent_code:
            raise BootstrapError("El bootstrap no contiene el código del agente.")
        if len(enrollment_token) < 16:
            raise BootstrapError("El token de enrolamiento del bootstrap es inválido.")
        return AgentBootstrap(base_url, agent_code, enrollment_token)
