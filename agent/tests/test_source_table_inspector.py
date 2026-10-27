import unittest

from bapps_sync_agent.infrastructure.source_config_store import SourceDatabaseConfig
from bapps_sync_agent.infrastructure.source_table_inspector import SourceTableInspector


class FakeStore:
    def __init__(self, config):
        self.config = config

    def load(self, _profile_ref):
        return self.config


class FakeCursor:
    description = [
        ("CODIGO", str),
        ("NOMBRE", str),
        ("ACTIVO", bool),
    ]

    def __init__(self, rows=None):
        self.query = ""
        self.closed = False
        self.rows = list(rows or [("V01", "Maria", True)])

    def execute(self, query):
        self.query = query

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, rows=None):
        self.cursor_instance = FakeCursor(rows)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class SourceTableInspectorTest(unittest.TestCase):
    def setUp(self):
        self.config = SourceDatabaseConfig(
            driver="firebird",
            host="localhost",
            port=3050,
            database="C:/Valery/Datos/VALERY3.MDF",
            username="reader",
            password="secret",
        )
        self.connection = FakeConnection()
        self.inspector = SourceTableInspector(
            FakeStore(self.config),
            connectors={"firebird": lambda _config: self.connection},
        )

    def test_returns_columns_types_and_one_sample_without_credentials(self):
        result = self.inspector.inspect({
            "profile_ref": "default",
            "driver": "firebird",
            "table": "VENDEDORES",
        })

        self.assertEqual(self.connection.cursor_instance.query, 'SELECT FIRST 2 SKIP 0 * FROM "VENDEDORES" ORDER BY 1')
        self.assertEqual([column["name"] for column in result["columns"]], ["CODIGO", "NOMBRE", "ACTIVO"])
        self.assertEqual(result["columns"][1]["sample"], "Maria")
        self.assertNotIn("password", result)
        self.assertNotIn("host", result)
        self.assertEqual(result["position"], 1)
        self.assertFalse(result["has_next"])
        self.assertTrue(self.connection.closed)

    def test_reads_a_requested_position_and_indicates_that_a_next_row_exists(self):
        self.connection = FakeConnection([("V08", "Sofia", True), ("V09", "Luis", False)])
        self.inspector = SourceTableInspector(
            FakeStore(self.config),
            connectors={"firebird": lambda _config: self.connection},
        )

        result = self.inspector.inspect({
            "profile_ref": "default",
            "driver": "firebird",
            "table": "VENDEDORES",
            "position": 8,
        })

        self.assertEqual(self.connection.cursor_instance.query, 'SELECT FIRST 2 SKIP 7 * FROM "VENDEDORES" ORDER BY 1')
        self.assertEqual(result["position"], 8)
        self.assertTrue(result["has_next"])
        self.assertEqual(result["columns"][0]["sample"], "V08")

    def test_rejects_an_out_of_range_position(self):
        with self.assertRaisesRegex(ValueError, "posici"):
            self.inspector.inspect({
                "profile_ref": "default",
                "driver": "firebird",
                "table": "VENDEDORES",
                "position": 10_001,
            })

    def test_rejects_untrusted_identifiers_before_connecting(self):
        with self.assertRaisesRegex(ValueError, "no es válido"):
            self.inspector.inspect({
                "profile_ref": "default",
                "driver": "firebird",
                "table": 'VENDEDORES"; DROP TABLE CLIENTES',
            })

        self.assertEqual(self.connection.cursor_instance.query, "")

    def test_rejects_a_profile_with_a_different_driver(self):
        self.config = SourceDatabaseConfig(
            driver="sqlserver",
            host="sql.test",
            port=1433,
            database="profit",
            username="reader",
            password="secret",
        )
        inspector = SourceTableInspector(
            FakeStore(self.config),
            connectors={"firebird": lambda _config: self.connection},
        )

        with self.assertRaisesRegex(RuntimeError, "SOURCE_DRIVER_MISMATCH"):
            inspector.inspect({
                "profile_ref": "default",
                "driver": "firebird",
                "table": "VENDEDORES",
            })


if __name__ == "__main__":
    unittest.main()
