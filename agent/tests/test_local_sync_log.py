import unittest
from datetime import datetime

from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.infrastructure.local_sync_log import LocalSyncLogRepository


class StaticConfigStore:
    def load_active_config(self):
        return {
            "targets": {"bapps_mysql": {
                "host": "mysql.test", "port": 3306, "database": "bapps",
                "username": "sync", "password": "target-secret",
            }},
        }


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query, params=None):
        self.connection.executed.append((query, params))

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.commits = 0
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class LocalSyncLogRepositoryTest(unittest.TestCase):
    def test_records_success_in_the_client_bapps_database(self):
        connection = FakeConnection()
        log = LocalSyncLogRepository(
            StaticConfigStore(), mysql_connect=lambda _target: connection,
            now=lambda: datetime(2026, 7, 23, 10, 0, 0),
        )

        log.record_success("clientes_valery", "RUN-1", SyncResult(rows_read=3, rows_inserted=2, rows_updated=1), 250)

        self.assertEqual(connection.commits, 1)
        self.assertTrue(connection.closed)
        self.assertEqual(sum(1 for query, _ in connection.executed if query.startswith("CREATE TABLE")), 2)
        insert, values = connection.executed[-1]
        self.assertIn("INSERT INTO `sync_success`", insert)
        self.assertEqual(values[1:4], ("clientes_valery_sync", "CLIENTES", "sync_success"))
        self.assertIn("leidos=3", values[4])

    def test_records_failure_without_exposing_credentials(self):
        connection = FakeConnection()
        log = LocalSyncLogRepository(StaticConfigStore(), mysql_connect=lambda _target: connection)

        log.record_error("clientes_valery", "RUN-2", SyncResult(error_code="SOURCE_DOWN", error_message="No disponible"), 100)

        insert, values = connection.executed[-1]
        self.assertIn("INSERT INTO `sync_errors`", insert)
        self.assertIn("codigo=SOURCE_DOWN", values[4])
        self.assertNotIn("target-secret", values[4])
