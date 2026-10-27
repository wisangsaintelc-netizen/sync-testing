import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig
from bapps_sync_agent.infrastructure.source_connection_tester import SourceConnectionTester
from bapps_sync_agent.syncs.declarative_table_reader import DeclarativeTableReaderSynchronizer
from bapps_sync_agent.ui_main import portable_self_test


class FakeProtector:
    def protect(self, value: str) -> str:
        return f"protected:{value[::-1]}"

    def unprotect(self, value: str) -> str:
        return value.removeprefix("protected:")[::-1]


class SourceConfigStoreTest(unittest.TestCase):
    def test_source_credentials_are_not_written_as_plain_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = SourceConfigStore(root, protector=FakeProtector())
            config = SourceDatabaseConfig(
                driver="firebird", host="10.0.0.15", port=3050,
                database="VALERY", username="sync", password="secret-value",
            )

            store.save(config)

            saved = (root / "config" / "source-database.json").read_text(encoding="utf-8")
            self.assertNotIn("secret-value", saved)
            self.assertIn('"secret_protection_scope":"machine"', saved)
            self.assertEqual(store.load(), config)

    def test_source_config_rejects_unknown_driver(self) -> None:
        config = SourceDatabaseConfig("oracle", "10.0.0.15", 1521, "SOURCE", "sync", "secret")

        with self.assertRaises(ValueError):
            config.validate()

    def test_named_sqlserver_profiles_are_stored_separately_and_protected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = SourceConfigStore(root, protector=FakeProtector())
            config = SourceDatabaseConfig(
                driver="sqlserver", host="profit.test", port=1433,
                database="PROFIT", username="sync_reader", password="secret-value",
            )

            store.save(config, "profit_principal")

            saved = (root / "config" / "source-databases" / "profit_principal.json").read_text(encoding="utf-8")
            self.assertNotIn("secret-value", saved)
            self.assertEqual(store.load("profit_principal"), config)

    def test_firebird_connection_uses_a_dsn(self) -> None:
        config = SourceDatabaseConfig(
            driver="firebird",
            host="localhost",
            port=3050,
            database=r"C:\\ValerySMB\\Datos\\VALERY3.MDF",
            username="SYSDBA",
            password="secret",
            charset="iso8859_1",
        )

        with patch("firebirdsql.connect") as connect:
            connection = connect.return_value
            SourceConnectionTester._test_firebird(config)

        connect.assert_called_once_with(
            host="localhost",
            port=3050,
            user="SYSDBA",
            password="secret",
            database=r"C:\\ValerySMB\\Datos\\VALERY3.MDF",
            charset="iso8859_1",
        )
        connection.cursor.return_value.execute.assert_called_once_with("SELECT 1 FROM RDB$DATABASE")
        connection.cursor.return_value.fetchone.assert_called_once()
        connection.cursor.return_value.close.assert_called_once()
        connection.close.assert_called_once()

    def test_declarative_firebird_reader_uses_snapshot_isolation(self) -> None:
        import firebirdsql

        config = SourceDatabaseConfig(
            driver="firebird",
            host="localhost",
            port=3050,
            database=r"C:\ValerySMB\Datos\VALERY3.MDF",
            username="reader",
            password="secret",
            charset="iso8859_1",
        )

        with patch("firebirdsql.connect") as connect:
            DeclarativeTableReaderSynchronizer._connect_firebird(config)

        self.assertEqual(
            connect.call_args.kwargs["isolation_level"],
            firebirdsql.ISOLATION_LEVEL_SNAPSHOT,
        )

    def test_charset_is_normalized_for_firebirdsql(self) -> None:
        self.assertEqual(SourceConnectionTester._normalize_firebirdsql_charset("ANSI_CHARSET"), "")
        self.assertEqual(SourceConnectionTester._normalize_firebirdsql_charset("cp1252"), "cp1252")
        self.assertEqual(SourceConnectionTester._normalize_firebirdsql_charset("UTF8"), "utf-8")

    def test_sqlserver_connection_requires_encryption_and_the_expected_port(self) -> None:
        config = SourceDatabaseConfig("sqlserver", "profit.test", 1433, "PROFIT", "reader", "secret")

        connection_string = SourceConnectionTester._sqlserver_connection_string(config)

        self.assertIn("SERVER=profit.test,1433", connection_string)
        self.assertIn("Encrypt=yes", connection_string)
        self.assertIn("TrustServerCertificate=no", connection_string)

    def test_portable_firebird_legacy_auth_dependencies(self) -> None:
        portable_self_test()
