import tempfile
import unittest
from pathlib import Path
from threading import Event

from bapps_sync_agent.domain.runs import SyncContext
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.source_config_store import SourceDatabaseConfig
from bapps_sync_agent.syncs.builtins import create_builtin_synchronizer_registry
from bapps_sync_agent.syncs.clientes_valery import ClientesValerySynchronizer, SOURCE_QUERY


class StaticSourceStore:
    def load(self):
        return SourceDatabaseConfig(
            driver="firebird", host="localhost", port=3050, database="C:/Valery/VALERY3.MDF",
            username="SYSDBA", password="source-secret", charset="iso8859_1",
        )


class StaticConfigStore:
    def load_active_config(self):
        return {
            "targets": {"bapps_mysql": {
                "host": "mysql.test", "port": 3306, "database": "bapps", "username": "sync", "password": "target-secret",
            }},
            "syncs": [{"code": "clientes_valery", "config": {"batch_size": 2}}],
        }


class FakeSourceCursor:
    description = [("CODIGO",), ("NOMBRE",)]

    def __init__(self):
        self.query = None
        self._batches = [[("001", "Ana"), ("002", "Bruno")], [("003", "Carla")], []]

    def execute(self, query):
        self.query = query

    def fetchmany(self, _size):
        return self._batches.pop(0)

    def close(self):
        pass


class FakeSourceConnection:
    def __init__(self):
        self.cursor_instance = FakeSourceCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class FakeTargetCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, query, params=None):
        self.connection.executed.append((query, params))
        if query.startswith("SHOW COLUMNS"):
            self.rows = [("id",), ("codigo",), ("nombre",), ("synced_at",)]
        elif query.startswith("SELECT `codigo`"):
            self.rows = [("001",)]
        else:
            self.rows = []

    def executemany(self, query, values):
        self.connection.executed.append((query, values))
        self.connection.upserts.append(values)

    def fetchall(self):
        return self.rows

    def close(self):
        pass


class FakeTargetConnection:
    def __init__(self):
        self.executed = []
        self.upserts = []
        self.commits = 0
        self.rolled_back = False

    def cursor(self):
        return FakeTargetCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class ClientesValerySynchronizerTest(unittest.TestCase):
    def test_builtin_registry_registers_clientes_valery_by_its_declared_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry = create_builtin_synchronizer_registry(Path(temporary), ConfigStore(Path(temporary)))

            self.assertIsInstance(registry.resolve(ClientesValerySynchronizer.CODE), ClientesValerySynchronizer)

    def test_reads_firebird_in_batches_and_upserts_by_codigo(self):
        source = FakeSourceConnection()
        target = FakeTargetConnection()
        synchronizer = ClientesValerySynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            firebird_connect=lambda _config: source,
            mysql_connect=lambda _config: target,
        )
        result = synchronizer.run(SyncContext("RUN-1", "CORR-1", "clientes_valery", "command", Event()))

        self.assertEqual(source.cursor_instance.query, SOURCE_QUERY)
        self.assertEqual(result.rows_read, 3)
        self.assertEqual(result.rows_inserted, 2)
        self.assertEqual(result.rows_updated, 1)
        self.assertEqual(len(target.upserts), 2)
        self.assertTrue(any(query.startswith("CREATE TABLE") for query, _params in target.executed))
        self.assertTrue(any("ON DUPLICATE KEY UPDATE" in query for query, _params in target.executed))

    def test_rejects_mysql_target_when_central_config_is_missing(self):
        class EmptyConfigStore:
            def load_active_config(self):
                return {"syncs": []}

        synchronizer = ClientesValerySynchronizer(StaticSourceStore(), EmptyConfigStore())
        with self.assertRaisesRegex(RuntimeError, "MySQL BAPPS"):
            synchronizer.run(SyncContext("RUN-1", "CORR-1", "clientes_valery", "command", Event()))

    def test_unavailable_mysql_target_is_detected_before_connecting_to_firebird(self):
        source_connected = False

        def connect_source(_config):
            nonlocal source_connected
            source_connected = True
            return FakeSourceConnection()

        def unavailable_target(_config):
            raise ConnectionError("MySQL BAPPS no disponible")

        synchronizer = ClientesValerySynchronizer(
            StaticSourceStore(), StaticConfigStore(),
            firebird_connect=connect_source,
            mysql_connect=unavailable_target,
        )

        with self.assertRaisesRegex(ConnectionError, "MySQL BAPPS no disponible"):
            synchronizer.run(SyncContext("RUN-1", "CORR-1", "clientes_valery", "command", Event()))

        self.assertFalse(source_connected)
