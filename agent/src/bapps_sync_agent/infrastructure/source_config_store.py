from dataclasses import asdict, dataclass
from pathlib import Path
import re

from .atomic_json import read_json, write_json_atomically
from .secret_protector import WindowsSecretProtector


@dataclass(frozen=True, slots=True)
class SourceDatabaseConfig:
    driver: str
    host: str
    port: int
    database: str
    username: str
    password: str
    charset: str = "iso8859_1"

    def validate(self) -> None:
        if self.driver not in {"firebird", "mysql", "sqlserver"}:
            raise ValueError("The source driver must be firebird, mysql, or sqlserver.")
        if not self.host.strip() or not self.database.strip() or not self.username.strip():
            raise ValueError("Host, database, and username are required.")
        if self.driver == "firebird" and not self.charset.strip():
            raise ValueError("A charset is required for Firebird.")
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535.")


class SourceConfigStore:
    def __init__(self, root: Path, protector: WindowsSecretProtector | None = None) -> None:
        self._path = root / "config" / "source-database.json"
        self._profiles_root = root / "config" / "source-databases"
        self._protector = protector or WindowsSecretProtector()

    def load(self, profile_ref: str = "default") -> SourceDatabaseConfig | None:
        data = read_json(self._profile_path(profile_ref), None)
        if data is None:
            return None
        password = self._protector.unprotect(str(data.pop("protected_password")))
        scope = data.pop("secret_protection_scope", None)
        # Kept only for compatibility with the first portable prototypes.
        data.pop("firebird_client_library", None)
        data.setdefault("charset", "iso8859_1")
        config = SourceDatabaseConfig(password=password, **data)
        if scope != "machine":
            self.save(config)
        return config

    def save(self, config: SourceDatabaseConfig, profile_ref: str = "default") -> None:
        config.validate()
        data = asdict(config)
        password = data.pop("password")
        data["protected_password"] = self._protector.protect(password)
        data["secret_protection_scope"] = "machine"
        write_json_atomically(self._profile_path(profile_ref), data)

    def _profile_path(self, profile_ref: str) -> Path:
        if profile_ref == "default":
            return self._path
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", profile_ref):
            raise ValueError("El identificador del perfil de origen es inválido.")
        return self._profiles_root / f"{profile_ref}.json"
