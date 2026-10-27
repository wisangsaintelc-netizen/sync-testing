from collections.abc import Callable
from datetime import datetime
from typing import Any

from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.infrastructure.bapps_mysql import (
    MysqlTargetConfig,
    connect_bapps_mysql,
    load_bapps_mysql_target,
)
from bapps_sync_agent.infrastructure.config_store import ConfigStore


class LocalSyncLogRepository:
    """Writes the F5 operational trail to the client's MySQL BAPPS database."""

    _TABLE_DETAILS = {
        "clientes_valery": ("clientes_valery_sync", "CLIENTES"),
    }

    def __init__(
        self,
        config_store: ConfigStore,
        mysql_connect: Callable[[MysqlTargetConfig], Any] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._config_store = config_store
        self._mysql_connect = mysql_connect or connect_bapps_mysql
        # MySQL DATETIME has no timezone. These are operational logs for the
        # client, so store the agent machine's wall-clock time rather than a
        # timezone-less UTC value that would look four hours ahead in Caracas.
        self._now = now or datetime.now

    def record_success(self, sync_code: str, run_id: str, result: SyncResult, duration_ms: int) -> None:
        target_table, source_table = self._details_for(sync_code)
        message = (
            f"run_id={run_id}; leidos={result.rows_read}; insertados={result.rows_inserted}; "
            f"actualizados={result.rows_updated}; fallidos={result.rows_failed}; duracion_ms={duration_ms}"
        )
        self._record("sync_success", target_table, source_table, "sync_success", message)

    def record_error(self, sync_code: str, run_id: str, result: SyncResult, duration_ms: int) -> None:
        target_table, source_table = self._details_for(sync_code)
        message = (
            f"run_id={run_id}; codigo={result.error_code or 'UNKNOWN'}; "
            f"detalle={result.error_message or 'Sin detalle'}; duracion_ms={duration_ms}"
        )
        self._record("sync_errors", target_table, source_table, "sync_failed", message)

    def _record(self, table: str, target_table: str, source_table: str, operation: str, message: str) -> None:
        connection = None
        try:
            connection = self._mysql_connect(load_bapps_mysql_target(self._config_store))
            cursor = connection.cursor()
            try:
                self._ensure_tables(cursor)
                cursor.execute(
                    f"INSERT INTO `{table}` (`datetime`, `mysql_table`, `sqlserver_table`, `operation`, `message`) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (self._now(), target_table, source_table, operation, message),
                )
                connection.commit()
            finally:
                cursor.close()
        except Exception:
            if connection is not None:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass

    @staticmethod
    def _details_for(sync_code: str) -> tuple[str, str]:
        return LocalSyncLogRepository._TABLE_DETAILS.get(sync_code, (sync_code, sync_code))

    @staticmethod
    def _ensure_tables(cursor: Any) -> None:
        for table in ("sync_success", "sync_errors"):
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS `{table}` ("
                "`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT, "
                "`datetime` DATETIME NOT NULL, "
                "`mysql_table` VARCHAR(128) NOT NULL, "
                "`sqlserver_table` VARCHAR(128) NOT NULL, "
                "`operation` VARCHAR(64) NOT NULL, "
                "`message` TEXT NOT NULL, "
                "PRIMARY KEY (`id`)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
            )
