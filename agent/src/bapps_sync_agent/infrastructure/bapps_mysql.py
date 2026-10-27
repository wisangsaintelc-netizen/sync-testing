from dataclasses import dataclass
from typing import Any

from bapps_sync_agent.infrastructure.config_store import ConfigStore


@dataclass(frozen=True, slots=True)
class MysqlTargetConfig:
    """The MySQL BAPPS destination published by the Control Center."""

    host: str
    port: int
    database: str
    username: str
    password: str

    def validate(self) -> None:
        if not self.host.strip() or not self.database.strip() or not self.username.strip() or not self.password:
            raise ValueError("La configuración MySQL BAPPS está incompleta.")
        if not 1 <= self.port <= 65535:
            raise ValueError("El puerto MySQL BAPPS debe estar entre 1 y 65535.")


def load_bapps_mysql_target(config_store: ConfigStore) -> MysqlTargetConfig:
    config = config_store.load_active_config() or {}
    targets = config.get("targets")
    target = targets.get("bapps_mysql") if isinstance(targets, dict) else None
    if not isinstance(target, dict):
        raise RuntimeError("Aún no se recibió la configuración MySQL BAPPS del Centro.")
    try:
        mysql = MysqlTargetConfig(
            host=str(target["host"]),
            port=int(target["port"]),
            database=str(target["database"]),
            username=str(target["username"]),
            password=str(target["password"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("La configuración MySQL BAPPS recibida es inválida.") from exc
    mysql.validate()
    return mysql


def connect_bapps_mysql(config: MysqlTargetConfig) -> Any:
    import pymysql

    return pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.username,
        password=config.password,
        database=config.database,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=10,
        read_timeout=30,
        write_timeout=30,
    )
