from dataclasses import dataclass

from .source_config_store import SourceDatabaseConfig


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    ok: bool
    message: str


class SourceConnectionTester:
    def test(self, config: SourceDatabaseConfig) -> ConnectionTestResult:
        try:
            config.validate()
            if config.driver == "mysql":
                self._test_mysql(config)
            elif config.driver == "sqlserver":
                self._test_sqlserver(config)
            else:
                self._test_firebird(config)
        except (ImportError, ModuleNotFoundError) as exc:
            missing = getattr(exc, "name", None) or str(exc)
            return ConnectionTestResult(
                False,
                f"Falta una dependencia del controlador {config.driver}: {missing}",
            )
        except Exception as exc:  # The UI must display the database driver's connection error.
            return ConnectionTestResult(False, str(exc))
        return ConnectionTestResult(True, "Conexión correcta.")

    @staticmethod
    def _test_mysql(config: SourceDatabaseConfig) -> None:
        import pymysql

        connection = pymysql.connect(
            host=config.host,
            port=config.port,
            user=config.username,
            password=config.password,
            database=config.database,
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
        )
        try:
            connection.ping(reconnect=False)
        finally:
            connection.close()

    @staticmethod
    def _test_firebird(config: SourceDatabaseConfig) -> None:
        """Use the pure-Python protocol driver so the portable needs no fbclient.dll."""
        import firebirdsql

        connection = firebirdsql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=config.password,
            charset=SourceConnectionTester._normalize_firebirdsql_charset(config.charset),
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1 FROM RDB$DATABASE")
                cursor.fetchone()
            finally:
                cursor.close()
        finally:
            connection.close()

    @staticmethod
    def _test_sqlserver(config: SourceDatabaseConfig) -> None:
        import pyodbc

        connection = pyodbc.connect(
            SourceConnectionTester._sqlserver_connection_string(config),
            timeout=5,
            autocommit=True,
        )
        try:
            cursor = connection.cursor()
            try:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            finally:
                cursor.close()
        finally:
            connection.close()

    @staticmethod
    def _sqlserver_connection_string(config: SourceDatabaseConfig) -> str:
        """ODBC Driver 18 keeps encryption mandatory for Profit connections."""
        return (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={config.host},{config.port};"
            f"DATABASE={config.database};UID={config.username};PWD={config.password};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=5;"
        )

    @staticmethod
    def _normalize_firebirdsql_charset(charset: str) -> str:
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
