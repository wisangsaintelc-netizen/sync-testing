import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from bapps_sync_agent.domain.runs import SyncContext
from bapps_sync_agent.domain.read_recipes import RecipeValidationError
from bapps_sync_agent.infrastructure.config_signature import ConfigSignatureError
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.syncs.builtins import create_builtin_synchronizer_registry
from bapps_sync_agent.infrastructure.source_config_store import SourceDatabaseConfig
from bapps_sync_agent.syncs.declarative_table_reader import DeclarativeTableReaderSynchronizer


class StaticSourceStore:
    def load(self, profile_ref: str):
        self.profile_ref = profile_ref
        return SourceDatabaseConfig("sqlserver", "profit.test", 1433, "PROFIT", "reader", "secret")


class StaticConfigStore:
    def load_active_config(self):
        return {
            "targets": {"bapps_mysql": {"host": "mysql.test", "port": 3306, "database": "bapps", "username": "sync", "password": "secret"}},
            "syncs": [{"code": "profit_factura", "config": {"recipe": {
                "schema_version": "1.0", "recipe_code": "profit_factura", "recipe_version": 1,
                "engine": "declarative_table_reader", "minimum_agent_version": "0.6.0",
                "source": {"profile_ref": "profit_principal", "driver": "sqlserver", "schema": "dbo", "table": "factura", "columns": ["fact_num", "fec_emis"]},
                "scope": {"where": {"operator": "date_window", "column": "fec_emis", "window": "current_calendar_year"}},
                "target": {"profile_ref": "bapps_mysql", "table": "factura_sync", "strategy": "full_snapshot", "ownership": "create_new"},
                "constants": {"sync": 1},
                "limits": {"batch_rows": 1000, "statement_timeout_seconds": 60, "max_runtime_seconds": 1800},
            }}}],
        }

    def load_identity(self):
        return None


class AllowConfigSignatureVerifier:
    def verify(self, _config, _identity):
        pass


class FakeSourceCursor:
    description = [("fact_num", str), ("fec_emis", str)]

    def __init__(self):
        self.executed = []
        self.batches = [[("F-001", "2026-01-01"), ("F-002", "2026-02-01")], []]

    def execute(self, sql, params=()):
        self.executed.append((sql, params))

    def fetchmany(self, _size):
        return self.batches.pop(0)

    def close(self):
        pass


class FakeSourceConnection:
    def __init__(self):
        self.cursor_instance = FakeSourceCursor()
        self.commits = 0

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.commits += 1

    def close(self):
        pass


class FailingSourceCursor(FakeSourceCursor):
    def fetchmany(self, _size):
        raise ConnectionError("Profit no disponible durante la lectura")


class FailingSourceConnection(FakeSourceConnection):
    def __init__(self):
        self.cursor_instance = FailingSourceCursor()
        self.commits = 0
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


class FakeTargetCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = []

    def execute(self, sql, params=None):
        self.connection.executed.append((sql, params))
        normalized = sql.lower()
        if "from `__bapps_sync_managed_tables`" in normalized:
            self.result = [(self.connection.recipe_code, self.connection.recipe_version)] if self.connection.managed else []
        elif "select `table_name` from information_schema.tables" in normalized:
            self.result = [(table_name,) for table_name in self.connection.stale_backups]
        elif "information_schema.tables" in normalized:
            self.result = [(1,)] if self.connection.target_exists else []
        elif "select count(*) from `__bapps_new_" in normalized:
            self.result = [(len(self.connection.loaded),)]
        else:
            self.result = []

    def executemany(self, sql, values):
        self.connection.executed.append((sql, values))
        self.connection.loaded = values

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result

    def close(self):
        pass


class FakeTargetConnection:
    def __init__(self, managed=False, target_exists=False, recipe_code="profit_factura", recipe_version=1, stale_backups=None):
        self.executed = []
        self.loaded = []
        self.commits = 0
        self.managed = managed
        self.target_exists = target_exists
        self.recipe_code = recipe_code
        self.recipe_version = recipe_version
        self.stale_backups = stale_backups or []

    def cursor(self):
        return FakeTargetCursor(self)

    def commit(self):
        self.commits += 1

    def close(self):
        pass


class DeclarativeTableReaderTest(unittest.TestCase):
    def test_reads_a_profit_snapshot_into_a_shadow_table_then_publishes(self):
        source = FakeSourceConnection()
        target = FakeTargetConnection()
        source_store = StaticSourceStore()
        synchronizer = DeclarativeTableReaderSynchronizer(
            source_store, StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: source},
            mysql_connect=lambda _config: target,
            today=lambda: date(2026, 7, 27),
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        result = synchronizer.run(SyncContext("RUN-1", "CORR-1", "profit_factura", "command", Event()))

        self.assertEqual(result.rows_read, 2)
        self.assertEqual(result.rows_inserted, 2)
        self.assertEqual(source_store.profile_ref, "profit_principal")
        self.assertTrue(any("SET TRANSACTION ISOLATION LEVEL SNAPSHOT" in query for query, _params in source.cursor_instance.executed))
        create_shadow = next(query for query, _params in target.executed if query.startswith("CREATE TABLE `__bapps_new_"))
        self.assertIn("`id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT", create_shadow)
        self.assertIn("PRIMARY KEY (`id`)", create_shadow)
        self.assertTrue(any(query.startswith("RENAME TABLE") for query, _params in target.executed))
        self.assertEqual(target.loaded, [("F-001", "2026-01-01", 1), ("F-002", "2026-02-01", 1)])

    def test_create_new_recipe_can_refresh_a_table_it_created_previously(self):
        source = FakeSourceConnection()
        target = FakeTargetConnection(managed=True, target_exists=True)
        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: source},
            mysql_connect=lambda _config: target,
            today=lambda: date(2026, 7, 27),
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        synchronizer.run(SyncContext("RUN-2", "CORR-2", "profit_factura", "schedule", Event()))

        rename = next(query for query, _params in target.executed if query.startswith("RENAME TABLE"))
        self.assertIn(" TO `__bapps_old_", rename)
        self.assertTrue(any(query.startswith("DROP TABLE IF EXISTS `__bapps_old_") for query, _params in target.executed))

    def test_removes_only_valid_stale_bapps_backups_before_loading(self):
        target = FakeTargetConnection(stale_backups=[
            "__bapps_old_0123456789abcdef",
            "__bapps_old_not_created_by_bapps",
            "vendedores",
        ])
        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: FakeSourceConnection()},
            mysql_connect=lambda _config: target,
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        synchronizer.run(SyncContext("RUN-CLEANUP", "CORR-CLEANUP", "profit_factura", "schedule", Event()))

        cleanup_queries = [query for query, _params in target.executed if query.startswith("DROP TABLE IF EXISTS")]
        self.assertIn("DROP TABLE IF EXISTS `__bapps_old_0123456789abcdef`", cleanup_queries)
        self.assertFalse(any("not_created_by_bapps" in query or "`vendedores`" in query for query in cleanup_queries))

    def test_profit_failure_drops_only_the_shadow_and_never_publishes_it(self):
        source = FailingSourceConnection()
        target = FakeTargetConnection()
        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: source},
            mysql_connect=lambda _config: target,
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        with self.assertRaisesRegex(ConnectionError, "Profit no disponible"):
            synchronizer.run(SyncContext("RUN-3", "CORR-3", "profit_factura", "schedule", Event()))

        self.assertFalse(any(query.startswith("RENAME TABLE") for query, _params in target.executed))
        self.assertTrue(any(query.startswith("DROP TABLE IF EXISTS `__bapps_new_") for query, _params in target.executed))
        self.assertEqual(source.rollbacks, 1)

    def test_managed_table_cannot_be_overwritten_by_another_recipe(self):
        target = FakeTargetConnection(managed=True, target_exists=True, recipe_code="otra_receta")
        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: FakeSourceConnection()},
            mysql_connect=lambda _config: target,
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        with self.assertRaisesRegex(RuntimeError, "TARGET_TABLE_OWNED_BY_OTHER_RECIPE"):
            synchronizer.run(SyncContext("RUN-OWNER", "CORR-OWNER", "profit_factura", "schedule", Event()))

        self.assertFalse(any(query.startswith("RENAME TABLE") for query, _params in target.executed))

    def test_unavailable_mysql_is_detected_before_connecting_to_profit(self):
        source_connected = False

        def connect_source(_config):
            nonlocal source_connected
            source_connected = True
            return FakeSourceConnection()

        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": connect_source},
            mysql_connect=lambda _config: (_ for _ in ()).throw(ConnectionError("MySQL BAPPS no disponible")),
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        with self.assertRaisesRegex(ConnectionError, "MySQL BAPPS no disponible"):
            synchronizer.run(SyncContext("RUN-4", "CORR-4", "profit_factura", "schedule", Event()))

        self.assertFalse(source_connected)

    def test_recipe_never_runs_from_an_unsigned_active_configuration(self):
        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            source_connectors={"sqlserver": lambda _config: FakeSourceConnection()},
            mysql_connect=lambda _config: FakeTargetConnection(),
        )

        with self.assertRaises(ConfigSignatureError):
            synchronizer.run(SyncContext("RUN-5", "CORR-5", "profit_factura", "schedule", Event()))

    def test_recipe_requires_an_agent_version_present_in_the_installed_binary(self):
        config = deepcopy(StaticConfigStore().load_active_config())
        config["syncs"][0]["config"]["recipe"]["minimum_agent_version"] = "0.8.0"

        class FutureRecipeConfigStore(StaticConfigStore):
            def load_active_config(self):
                return config

        synchronizer = DeclarativeTableReaderSynchronizer(
            StaticSourceStore(), FutureRecipeConfigStore(),
            source_connectors={"sqlserver": lambda _config: FakeSourceConnection()},
            mysql_connect=lambda _config: FakeTargetConnection(),
            config_signature_verifier=AllowConfigSignatureVerifier(),
        )

        with self.assertRaisesRegex(RecipeValidationError, "AGENT_VERSION_UNSUPPORTED"):
            synchronizer.run(SyncContext("RUN-VERSION", "CORR-VERSION", "profit_factura", "schedule", Event()))

    def test_registry_resolves_a_declarative_recipe_without_a_per_table_python_file(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root)
            config = StaticConfigStore().load_active_config()
            store.save_active_config(config)

            synchronizer = create_builtin_synchronizer_registry(root, store).resolve("profit_factura")

            self.assertIsInstance(synchronizer, DeclarativeTableReaderSynchronizer)
