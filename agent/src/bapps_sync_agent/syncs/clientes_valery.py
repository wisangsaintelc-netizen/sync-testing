from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Iterable

from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.domain.runs import SyncContext
from bapps_sync_agent.infrastructure.bapps_mysql import MysqlTargetConfig, connect_bapps_mysql, load_bapps_mysql_target
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig


SYNC_CODE = "clientes_valery"
SOURCE_QUERY = "SELECT * FROM CLIENTES ORDER BY CODIGO"
TARGET_TABLE = "clientes_valery_sync"


class ClientesValerySynchronizer:
    """Read-only Firebird CLIENTES reader with idempotent MySQL upserts by CODIGO."""

    CODE = SYNC_CODE

    def __init__(
        self,
        source_store: SourceConfigStore,
        config_store: ConfigStore,
        firebird_connect: Callable[[SourceDatabaseConfig], Any] | None = None,
        mysql_connect: Callable[[MysqlTargetConfig], Any] | None = None,
    ) -> None:
        self._source_store = source_store
        self._config_store = config_store
        self._firebird_connect = firebird_connect or self._connect_firebird
        self._mysql_connect = mysql_connect or self._connect_mysql

    def run(self, context: SyncContext) -> SyncResult:
        source = self._load_source()
        target = self._load_target()
        batch_size = self._batch_size()
        source_connection = None
        target_connection = None
        rows_read = rows_inserted = rows_updated = 0

        try:
            context.raise_if_stopped()
            target_connection = self._mysql_connect(target)
            source_connection = self._firebird_connect(source)
            source_cursor = source_connection.cursor()
            try:
                # This is deliberately the only Firebird statement in the synchronizer.
                source_cursor.execute(SOURCE_QUERY)
                columns = [str(description[0]).strip().lower() for description in source_cursor.description]
                if "codigo" not in columns:
                    raise RuntimeError("CLIENTES no contiene CODIGO; no es posible hacer upsert seguro.")

                table_ready = False
                while True:
                    context.raise_if_stopped()
                    raw_rows = source_cursor.fetchmany(batch_size)
                    if not raw_rows:
                        break
                    rows = [self._normalize_row(columns, row) for row in raw_rows]
                    if not table_ready:
                        self._ensure_target_table(target_connection, columns, rows)
                        table_ready = True
                    inserted, updated = self._upsert_batch(target_connection, columns, rows)
                    rows_read += len(rows)
                    rows_inserted += inserted
                    rows_updated += updated
                    context.raise_if_stopped()
            finally:
                source_cursor.close()

            return SyncResult(
                rows_read=rows_read,
                rows_inserted=rows_inserted,
                rows_updated=rows_updated,
            )
        except Exception:
            if target_connection is not None:
                target_connection.rollback()
            raise
        finally:
            self._close_quietly(source_connection)
            self._close_quietly(target_connection)

    def _load_source(self) -> SourceDatabaseConfig:
        source = self._source_store.load()
        if source is None:
            raise RuntimeError("Configura primero la fuente Firebird de Valery.")
        if source.driver != "firebird":
            raise RuntimeError("clientes_valery requiere una fuente Firebird.")
        source.validate()
        return source

    def _load_target(self) -> MysqlTargetConfig:
        return load_bapps_mysql_target(self._config_store)

    def _batch_size(self) -> int:
        config = self._config_store.load_active_config() or {}
        syncs = config.get("syncs")
        if isinstance(syncs, list):
            for sync in syncs:
                if isinstance(sync, dict) and sync.get("code") == SYNC_CODE:
                    details = sync.get("config")
                    if isinstance(details, dict):
                        try:
                            return max(1, min(1_000, int(details.get("batch_size", 200))))
                        except (TypeError, ValueError):
                            break
        return 200

    @staticmethod
    def _connect_firebird(config: SourceDatabaseConfig) -> Any:
        import firebirdsql

        return firebirdsql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=config.password,
            charset=ClientesValerySynchronizer._firebird_charset(config.charset),
        )

    @staticmethod
    def _connect_mysql(config: MysqlTargetConfig) -> Any:
        return connect_bapps_mysql(config)

    def _ensure_target_table(self, connection: Any, columns: list[str], rows: list[dict[str, Any]]) -> None:
        cursor = connection.cursor()
        try:
            column_definitions = ["`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT"]
            for column in columns:
                nullable = "NOT NULL" if column == "codigo" else "NULL"
                column_definitions.append(f"{self._quote(column)} {self._mysql_type(column, rows)} {nullable}")
            column_definitions.extend([
                "`synced_at` DATETIME NOT NULL",
                "PRIMARY KEY (`id`)",
                "UNIQUE KEY `uq_clientes_valery_codigo` (`codigo`)",
            ])
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS `{TARGET_TABLE}` ({', '.join(column_definitions)}) "
                "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
            )
            cursor.execute(f"SHOW COLUMNS FROM `{TARGET_TABLE}`")
            existing = {str(row[0]).lower() for row in cursor.fetchall()}
            for column in columns:
                if column not in existing:
                    cursor.execute(
                        f"ALTER TABLE `{TARGET_TABLE}` ADD COLUMN {self._quote(column)} {self._mysql_type(column, rows)} NULL"
                    )
            if "synced_at" not in existing:
                cursor.execute(f"ALTER TABLE `{TARGET_TABLE}` ADD COLUMN `synced_at` DATETIME NOT NULL")
            connection.commit()
        finally:
            cursor.close()

    def _upsert_batch(self, connection: Any, columns: list[str], rows: list[dict[str, Any]]) -> tuple[int, int]:
        codes = [str(row["codigo"]) for row in rows if row.get("codigo") not in (None, "")]
        if len(codes) != len(rows):
            raise RuntimeError("CLIENTES contiene un CODIGO vacío; se abortó para preservar la idempotencia.")
        cursor = connection.cursor()
        try:
            placeholders = ", ".join(["%s"] * len(codes))
            cursor.execute(
                f"SELECT `codigo` FROM `{TARGET_TABLE}` WHERE `codigo` IN ({placeholders})",
                tuple(codes),
            )
            existing = {str(row[0]) for row in cursor.fetchall()}
            all_columns = [*columns, "synced_at"]
            values_placeholders = ", ".join(["%s"] * len(all_columns))
            columns_sql = ", ".join(self._quote(column) for column in all_columns)
            updates = ", ".join(
                f"{self._quote(column)}=VALUES({self._quote(column)})" for column in all_columns if column != "codigo"
            )
            cursor.executemany(
                f"INSERT INTO `{TARGET_TABLE}` ({columns_sql}) VALUES ({values_placeholders}) "
                f"ON DUPLICATE KEY UPDATE {updates}",
                [tuple([row.get(column) for column in columns] + [datetime.now()]) for row in rows],
            )
            connection.commit()
            updated = sum(1 for code in codes if code in existing)
            return len(rows) - updated, updated
        finally:
            cursor.close()

    @staticmethod
    def _normalize_row(columns: list[str], row: Iterable[Any]) -> dict[str, Any]:
        return {column: ClientesValerySynchronizer._normalize_value(value) for column, value in zip(columns, row)}

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, bytes):
            return value.decode("latin-1", errors="replace")
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _mysql_type(column: str, rows: list[dict[str, Any]]) -> str:
        if column == "codigo":
            return "VARCHAR(64)"
        values = [row[column] for row in rows if row.get(column) is not None]
        if not values:
            return "TEXT"
        if all(isinstance(value, bool) for value in values):
            return "TINYINT(1)"
        if all(isinstance(value, int) and not isinstance(value, bool) for value in values):
            return "BIGINT"
        if all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
            return "DECIMAL(18,4)"
        if all(isinstance(value, datetime) for value in values):
            return "DATETIME"
        if all(isinstance(value, date) for value in values):
            return "DATE"
        return "VARCHAR(255)" if max(len(str(value)) for value in values) <= 255 else "TEXT"

    @staticmethod
    def _quote(identifier: str) -> str:
        return f"`{identifier.replace('`', '``')}`"

    @staticmethod
    def _firebird_charset(charset: str) -> str:
        normalized = charset.strip().upper()
        if normalized in {"", "NONE", "ANSI_CHARSET"}:
            return ""
        if normalized in {"WIN1252", "WINDOWS-1252", "CP1252"}:
            return "cp1252"
        if normalized in {"ISO8859_1", "ISO-8859-1", "LATIN1"}:
            return "iso8859_1"
        if normalized in {"UTF8", "UTF-8"}:
            return "utf-8"
        return charset

    @staticmethod
    def _close_quietly(connection: Any) -> None:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
