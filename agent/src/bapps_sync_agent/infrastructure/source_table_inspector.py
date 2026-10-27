from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
import re
from typing import Any, Callable, Mapping

from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_$]{0,62}")
_MAX_COLUMNS = 256
_MAX_SAMPLE_CHARACTERS = 500
_MAX_PREVIEW_POSITION = 10_000


class SourceTableInspector:
    """Read one source row using an agent-local protected database profile."""

    def __init__(
        self,
        source_store: SourceConfigStore,
        connectors: Mapping[str, Callable[[SourceDatabaseConfig], Any]] | None = None,
    ) -> None:
        self._source_store = source_store
        self._connectors = connectors or {
            "firebird": self._connect_firebird,
            "sqlserver": self._connect_sqlserver,
        }

    def inspect(self, payload: dict[str, object]) -> dict[str, object]:
        profile_ref = self._identifier(payload, "profile_ref", allow_dash=True)
        driver = str(payload.get("driver", ""))
        if driver not in self._connectors:
            raise ValueError("El motor solicitado no está permitido.")
        table = self._identifier(payload, "table")
        position = self._position(payload)
        schema = self._identifier(payload, "schema") if driver == "sqlserver" else None
        if driver == "sqlserver" and schema is None:
            schema = "dbo"

        config = self._source_store.load(profile_ref)
        if config is None:
            raise RuntimeError(f"SOURCE_PROFILE_NOT_FOUND: no existe el perfil local {profile_ref}.")
        config.validate()
        if config.driver != driver:
            raise RuntimeError(
                f"SOURCE_DRIVER_MISMATCH: el perfil {profile_ref} usa {config.driver}, no {driver}."
            )

        connection = None
        cursor = None
        try:
            connection = self._connectors[driver](config)
            cursor = connection.cursor()
            cursor.execute(self._preview_query(driver, schema, table, position))
            description = tuple(cursor.description or ())
            if not description:
                raise RuntimeError("SOURCE_TABLE_HAS_NO_COLUMNS: la tabla no expuso columnas.")
            if len(description) > _MAX_COLUMNS:
                raise RuntimeError(
                    f"SOURCE_TABLE_TOO_WIDE: la tabla tiene {len(description)} columnas; "
                    f"el límite de inspección es {_MAX_COLUMNS}."
                )
            row = cursor.fetchone()
            has_next = cursor.fetchone() is not None if row is not None else False
            columns = []
            for index, item in enumerate(description):
                columns.append({
                    "name": str(item[0]).strip(),
                    "type": self._type_name(item),
                    "sample": self._sample_value(row[index]) if row is not None else None,
                })
            return {
                "driver": driver,
                "profile_ref": profile_ref,
                "schema": schema,
                "table": table,
                "position": position,
                "has_row": row is not None,
                "has_next": has_next,
                "columns": columns,
            }
        except (RuntimeError, ValueError):
            raise
        except Exception as exc:
            raise RuntimeError(f"SOURCE_INSPECTION_FAILED: {str(exc)[:500]}") from exc
        finally:
            self._close_quietly(cursor)
            self._close_quietly(connection)

    @staticmethod
    def _identifier(
        payload: dict[str, object],
        key: str,
        *,
        allow_dash: bool = False,
    ) -> str | None:
        raw = payload.get(key)
        if raw is None and key == "schema":
            return None
        if not isinstance(raw, str) or not raw:
            raise ValueError(f"Falta el identificador {key}.")
        pattern = r"[A-Za-z_][A-Za-z0-9_-]{0,63}" if allow_dash else _IDENTIFIER
        if re.fullmatch(pattern, raw) is None:
            raise ValueError(f"El identificador {key} no es válido.")
        return raw

    @staticmethod
    def _position(payload: dict[str, object]) -> int:
        position = payload.get("position", 1)
        if isinstance(position, bool) or not isinstance(position, int):
            raise ValueError("La posición de inspección no es válida.")
        if not 1 <= position <= _MAX_PREVIEW_POSITION:
            raise ValueError(
                f"La posición de inspección debe estar entre 1 y {_MAX_PREVIEW_POSITION}."
            )
        return position

    @staticmethod
    def _preview_query(driver: str, schema: str | None, table: str, position: int) -> str:
        if driver == "firebird":
            return f'SELECT FIRST 2 SKIP {position - 1} * FROM "{table}" ORDER BY 1'
        return (
            f"SELECT * FROM [{schema}].[{table}] ORDER BY 1 "
            f"OFFSET {position - 1} ROWS FETCH NEXT 2 ROWS ONLY"
        )

    @staticmethod
    def _type_name(description: Any) -> str:
        type_code = description[1] if len(description) > 1 else None
        return getattr(type_code, "__name__", str(type_code))[:128]

    @staticmethod
    def _sample_value(value: Any) -> object:
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (date, datetime, time)):
            return value.isoformat()
        if isinstance(value, bytes):
            return f"<binario: {len(value)} bytes>"
        if isinstance(value, str):
            return value[:_MAX_SAMPLE_CHARACTERS]
        return f"<{type(value).__name__}>"

    @staticmethod
    def _connect_firebird(config: SourceDatabaseConfig) -> Any:
        import firebirdsql

        return firebirdsql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=config.password,
            charset=config.charset,
            isolation_level=firebirdsql.ISOLATION_LEVEL_SNAPSHOT,
        )

    @staticmethod
    def _connect_sqlserver(config: SourceDatabaseConfig) -> Any:
        import pyodbc

        connection_string = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={config.host},{config.port};DATABASE={config.database};"
            f"UID={config.username};PWD={config.password};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=10;"
        )
        return pyodbc.connect(connection_string, timeout=10, autocommit=False)

    @staticmethod
    def _close_quietly(resource: Any) -> None:
        if resource is None:
            return
        try:
            resource.close()
        except Exception:
            pass
