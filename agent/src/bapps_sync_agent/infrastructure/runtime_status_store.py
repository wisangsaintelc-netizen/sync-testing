from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .atomic_json import read_json, write_json_atomically


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    state: str = "waiting"
    message: str = "Esperando enrolamiento"
    last_heartbeat_at: str | None = None
    config_version: int | None = None
    config_error: str | None = None


class RuntimeStatusStore:
    def __init__(self, root: Path) -> None:
        self._path = root / "state" / "runtime-status.json"

    def load(self) -> RuntimeStatus:
        data = read_json(self._path, None)
        return RuntimeStatus(**data) if isinstance(data, dict) else RuntimeStatus()

    def save(self, status: RuntimeStatus) -> None:
        write_json_atomically(self._path, asdict(status))

    def mark_online(self, config_version: int) -> None:
        """Record a valid configuration without conflating it with heartbeat health."""
        current = self.load()
        self.save(RuntimeStatus(
            state="online",
            message="Conectado al Centro BAPPS.",
            last_heartbeat_at=current.last_heartbeat_at,
            config_version=config_version,
            config_error=None,
        ))

    def mark_heartbeat_online(self, config_version: int) -> None:
        current = self.load()
        if current.config_error is not None:
            self.save(RuntimeStatus(
                state="degraded",
                message=current.config_error,
                last_heartbeat_at=datetime.now(UTC).isoformat(),
                config_version=config_version,
                config_error=current.config_error,
            ))
            return
        self.save(RuntimeStatus(
            state="online",
            message="Conectado al Centro BAPPS.",
            last_heartbeat_at=datetime.now(UTC).isoformat(),
            config_version=config_version,
            config_error=None,
        ))

    def mark_config_error(self, message: str) -> None:
        current = self.load()
        self.save(RuntimeStatus(
            state="degraded" if current.last_heartbeat_at is not None else "offline",
            message=message,
            last_heartbeat_at=current.last_heartbeat_at,
            config_version=current.config_version,
            config_error=message,
        ))

    def mark_error(self, message: str) -> None:
        current = self.load()
        self.save(RuntimeStatus(
            state="offline",
            message=message,
            last_heartbeat_at=current.last_heartbeat_at,
            config_version=current.config_version,
            config_error=current.config_error,
        ))
