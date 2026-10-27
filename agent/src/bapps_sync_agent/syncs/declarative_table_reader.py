"""The one read-only table engine used by declarative recipes.

It is intentionally separate from the current Valery synchronizer while the
Control Center signing flow is completed.  The class is fully testable with
fake DB-API connections and has no table-specific SQL in it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import re
from typing import Any, Callable, Iterable, Mapping

from bapps_sync_agent.domain.read_recipes import ReadRecipe, RecipeValidationError, recipe_for_sync
from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.domain.runs import SyncContext
from bapps_sync_agent.infrastructure.bapps_mysql import MysqlTargetConfig, connect_bapps_mysql, load_bapps_mysql_target
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.config_signature import ConfigSignatureVerifier
from bapps_sync_agent.infrastructure.read_recipe_query import compile_read_query
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig


class DeclarativeTableReaderSynchronizer:
    """Copies a validated source snapshot to an agent-owned MySQL shadow table."""

    def __init__(
        self,
        source_store: SourceConfigStore,
        config_store: ConfigStore,
        source_connectors: Mapping[str, Callable[[SourceDatabaseConfig], Any]] | None = None,
        mysql_connect: Callable[[MysqlTargetConfig], Any] | None = None,
        today: Callable[[], date] | None = None,
        config_signature_verifier: ConfigSignatureVerifier | None = None,
    ) -> None:
        self._source_store = source_store
        self._config_store = config_store
        self._source_connectors = source_connectors or {
            "firebird": self._connect_firebird,
            "sqlserver": self._connect_sqlserver,
        }
        self._mysql_connect = mysql_connect or connect_bapps_mysql
        self._today = today or date.today
        self._config_signature_verifier = config_signature_verifier or ConfigSignatureVerifier()

    def run(self, context: SyncContext) -> SyncResult:
        active_config = self._config_store.load_active_config() or {}
        self._config_signature_verifier.verify(active_config, self._config_store.load_identity())
        recipe = recipe_for_sync(active_config, context.sync_code)
        self._ensure_agent_version(recipe)
        source = self._load_source(recipe)
        target = self._load_target(recipe)
        connector = self._source_connectors.get(recipe.source.driver)
        if connector is None:
            raise RuntimeError(f"El agente no incluye el conector {recipe.source.driver} requerido por la receta.")

        target_connection = None
        source_connection = None
        publisher: SnapshotTablePublisher | None = None
        rows_read = 0
        try:
            context.raise_if_stopped()
            # Target first: do not put load on Profit if the destination is unavailable.
            target_connection = self._mysql_connect(target)
            publisher = SnapshotTablePublisher(target_connection, recipe, context.run_id)
            publisher.preflight()

            source_connection = connector(source)
            source_cursor = source_connection.cursor()
            try:
                self._begin_consistent_read(source_connection, recipe.source.driver)
                query = compile_read_query(recipe, today=self._today())
                source_cursor.execute(query.sql, query.params)
                columns = tuple(str(description[0]).strip() for description in source_cursor.description)
                if tuple(column.lower() for column in columns) != tuple(column.lower() for column in recipe.source.columns):
                    raise RuntimeError("SOURCE_SCHEMA_MISMATCH: la proyección real no coincide con la receta publicada.")
                publisher.begin(columns, source_cursor.description)
                while True:
                    context.raise_if_stopped()
                    raw_rows = source_cursor.fetchmany(recipe.batch_rows)
                    if not raw_rows:
                        break
                    rows = [self._normalize_row(columns, row, recipe.constants) for row in raw_rows]
                    publisher.write(rows)
                    rows_read += len(rows)
                self._finish_consistent_read(source_connection, recipe.source.driver)
            finally:
                source_cursor.close()

            publisher.validate(rows_read)
            publisher.publish()
            return SyncResult(rows_read=rows_read, rows_inserted=rows_read)
        except Exception:
            if publisher is not None:
                try:
                    publisher.abort()
                except Exception:
                    pass
            if source_connection is not None and recipe.source.driver == "sqlserver":
                try:
                    source_connection.rollback()
                except Exception:
                    pass
            raise
        finally:
            self._close_quietly(source_connection)
            self._close_quietly(target_connection)

    def _load_source(self, recipe: ReadRecipe) -> SourceDatabaseConfig:
        source = self._source_store.load(recipe.source.profile_ref)
        if source is None:
            raise RuntimeError(f"No está configurado el perfil local de origen {recipe.source.profile_ref}.")
        source.validate()
        if source.driver != recipe.source.driver:
            raise RecipeValidationError(
                f"El perfil {recipe.source.profile_ref} es {source.driver}, pero la receta requiere {recipe.source.driver}."
            )
        return source

    def _load_target(self, recipe: ReadRecipe) -> MysqlTargetConfig:
        if recipe.target.profile_ref != "bapps_mysql":
            raise RecipeValidationError("La receta v1 solo admite el destino local bapps_mysql.")
        return load_bapps_mysql_target(self._config_store)

    @staticmethod
    def _begin_consistent_read(connection: Any, driver: str) -> None:
        if driver != "sqlserver":
            return
        cursor = connection.cursor()
        try:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL SNAPSHOT")
            cursor.execute("BEGIN TRANSACTION")
        finally:
            cursor.close()

    @staticmethod
    def _finish_consistent_read(connection: Any, driver: str) -> None:
        if driver == "sqlserver":
            connection.commit()

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
    def _normalize_row(columns: Iterable[str], values: Iterable[Any], constants: Mapping[str, Any]) -> dict[str, Any]:
        row = {column: DeclarativeTableReaderSynchronizer._normalize_value(value) for column, value in zip(columns, values)}
        row.update(constants)
        return row

    @staticmethod
    def _normalize_value(value: Any) -> Any:
        if isinstance(value, bytes):
            return value
        if isinstance(value, Decimal):
            return value
        if isinstance(value, str):
            return value.strip()
        return value

    @staticmethod
    def _close_quietly(connection: Any) -> None:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

    @staticmethod
    def _ensure_agent_version(recipe: ReadRecipe) -> None:
        from bapps_sync_agent import __version__

        installed = tuple(int(part) for part in __version__.split("."))
        required = tuple(int(part) for part in recipe.minimum_agent_version.split("."))
        if installed < required:
            raise RecipeValidationError(
                f"AGENT_VERSION_UNSUPPORTED: la receta requiere {recipe.minimum_agent_version} "
                f"y este agente es {__version__}."
            )


class SnapshotTablePublisher:
    """Publishes a complete MySQL table only after a shadow load succeeds."""

    _METADATA_TABLE = "__bapps_sync_managed_tables"
    _STALE_BACKUP_NAME = re.compile(r"__bapps_old_[0-9a-f]{16}")

    def __init__(self, connection: Any, recipe: ReadRecipe, run_id: str) -> None:
        self._connection = connection
        self._recipe = recipe
        digest = sha256(f"{recipe.target.table}:{run_id}".encode()).hexdigest()[:16]
        self._shadow = f"__bapps_new_{digest}"
        self._backup = f"__bapps_old_{digest}"
        self._columns: tuple[str, ...] = ()
        self._created_shadow = False

    def preflight(self) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS `{self._METADATA_TABLE}` ("
                "`table_name` VARCHAR(64) NOT NULL PRIMARY KEY,"
                "`recipe_code` VARCHAR(128) NOT NULL,"
                "`recipe_version` INT NOT NULL,"
                "`state` VARCHAR(16) NOT NULL,"
                "`updated_at` DATETIME NOT NULL"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
            cursor.execute(
                f"SELECT `recipe_code`, `recipe_version` FROM `{self._METADATA_TABLE}` WHERE `table_name` = %s",
                (self._recipe.target.table,),
            )
            managed_row = cursor.fetchone()
            managed = managed_row is not None
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
                (self._recipe.target.table,),
            )
            target_exists = cursor.fetchone() is not None
            if target_exists and not managed:
                raise RuntimeError("TARGET_TABLE_NOT_MANAGED: BAPPS Sync no administra la tabla destino.")
            if managed and str(managed_row[0]) != self._recipe.recipe_code:
                raise RuntimeError("TARGET_TABLE_OWNED_BY_OTHER_RECIPE: la tabla pertenece a otra receta.")
            if managed and int(managed_row[1]) > self._recipe.recipe_version:
                raise RuntimeError("RECIPE_ROLLBACK_NOT_ALLOWED: la tabla fue publicada con una receta posterior.")
            if self._recipe.target.ownership == "managed_only" and not managed:
                raise RuntimeError("TARGET_TABLE_NOT_MANAGED: la receta exige una tabla previamente administrada.")
            if self._recipe.target.ownership == "create_new" and target_exists and not managed:
                raise RuntimeError("TARGET_TABLE_ALREADY_EXISTS: create_new no adopta tablas existentes.")
            self._cleanup_stale_backups(cursor)
            self._connection.commit()
        finally:
            cursor.close()

    def begin(self, columns: tuple[str, ...], description: Any) -> None:
        self._columns = (*columns, *self._recipe.constants.keys())
        if any(column.lower() == "id" for column in self._columns):
            raise RecipeValidationError(
                "TARGET_RESERVED_COLUMN: id está reservado para la clave autoincremental del destino MySQL."
            )
        definitions = ["`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT"]
        definitions.extend(f"{self._quote(column)} {self._mysql_type(item)} NULL" for column, item in zip(columns, description))
        definitions.extend(f"{self._quote(column)} {self._mysql_value_type(value)} NULL" for column, value in self._recipe.constants.items())
        definitions.append("PRIMARY KEY (`id`)")
        cursor = self._connection.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {self._quote(self._shadow)}")
            cursor.execute(
                f"CREATE TABLE {self._quote(self._shadow)} ({', '.join(definitions)}) "
                "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
            )
            self._created_shadow = True
            self._connection.commit()
        finally:
            cursor.close()

    def write(self, rows: list[Mapping[str, Any]]) -> None:
        if not rows:
            return
        placeholders = ", ".join("%s" for _ in self._columns)
        columns_sql = ", ".join(self._quote(column) for column in self._columns)
        cursor = self._connection.cursor()
        try:
            cursor.executemany(
                f"INSERT INTO {self._quote(self._shadow)} ({columns_sql}) VALUES ({placeholders})",
                [tuple(row.get(column) for column in self._columns) for row in rows],
            )
            self._connection.commit()
        finally:
            cursor.close()

    def validate(self, expected_rows: int) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {self._quote(self._shadow)}")
            result = cursor.fetchone()
            loaded_rows = int(result[0]) if result is not None else -1
            if loaded_rows != expected_rows:
                raise RuntimeError(
                    f"TARGET_ROW_COUNT_MISMATCH: se leyeron {expected_rows} filas y la sombra contiene {loaded_rows}."
                )
        finally:
            cursor.close()

    def publish(self) -> None:
        cursor = self._connection.cursor()
        try:
            cursor.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = %s",
                (self._recipe.target.table,),
            )
            target_exists = cursor.fetchone() is not None
            if not target_exists:
                cursor.execute(f"RENAME TABLE {self._quote(self._shadow)} TO {self._quote(self._recipe.target.table)}")
            else:
                cursor.execute(
                    f"RENAME TABLE {self._quote(self._recipe.target.table)} TO {self._quote(self._backup)}, "
                    f"{self._quote(self._shadow)} TO {self._quote(self._recipe.target.table)}"
                )
            cursor.execute(
                f"INSERT INTO `{self._METADATA_TABLE}` (`table_name`, `recipe_code`, `recipe_version`, `state`, `updated_at`) "
                "VALUES (%s, %s, %s, 'active', %s) ON DUPLICATE KEY UPDATE "
                "`recipe_code`=VALUES(`recipe_code`), `recipe_version`=VALUES(`recipe_version`), "
                "`state`='active', `updated_at`=VALUES(`updated_at`)",
                (self._recipe.target.table, self._recipe.recipe_code, self._recipe.recipe_version, datetime.now()),
            )
            self._connection.commit()
            self._created_shadow = False
            if target_exists:
                cursor.execute(f"DROP TABLE IF EXISTS {self._quote(self._backup)}")
                self._connection.commit()
        finally:
            cursor.close()

    def abort(self) -> None:
        if not self._created_shadow:
            return
        cursor = self._connection.cursor()
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {self._quote(self._shadow)}")
            self._connection.commit()
        finally:
            cursor.close()

    def _cleanup_stale_backups(self, cursor: Any) -> None:
        """Remove only backups created by this engine after a prior publish."""
        cursor.execute(
            "SELECT `table_name` FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name LIKE %s",
            ("__bapps_old_%",),
        )
        for row in cursor.fetchall():
            table_name = str(row[0])
            if self._STALE_BACKUP_NAME.fullmatch(table_name) is not None:
                cursor.execute(f"DROP TABLE IF EXISTS {self._quote(table_name)}")

    @staticmethod
    def _mysql_type(description: Any) -> str:
        type_code = description[1] if len(description) > 1 else None
        name = getattr(type_code, "__name__", str(type_code)).lower()
        if "bool" in name:
            return "TINYINT(1)"
        if "int" in name:
            return "BIGINT"
        if "decimal" in name or "numeric" in name:
            return "DECIMAL(38, 10)"
        if "float" in name or "double" in name or "real" in name:
            return "DOUBLE"
        if "datetime" in name or "timestamp" in name:
            return "DATETIME(6)"
        if name == "date" or name.endswith(".date"):
            return "DATE"
        if "binary" in name or "bytes" in name:
            return "LONGBLOB"
        return "TEXT"

    @staticmethod
    def _mysql_value_type(value: Any) -> str:
        if isinstance(value, bool):
            return "TINYINT(1)"
        if isinstance(value, int):
            return "BIGINT"
        if isinstance(value, float):
            return "DOUBLE"
        return "TEXT"

    @staticmethod
    def _quote(identifier: str) -> str:
        return f"`{identifier.replace('`', '``')}`"
