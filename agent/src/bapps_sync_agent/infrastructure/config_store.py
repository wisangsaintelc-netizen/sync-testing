from copy import deepcopy
from dataclasses import dataclass, field, replace
from base64 import b64decode
from binascii import Error as Base64Error
import json
from pathlib import Path
import re
from typing import Any

from .atomic_json import read_json, write_json_atomically
from .secret_protector import WindowsSecretProtector


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    agent_code: str
    agent_token: str
    base_url: str
    config_signing_public_key: str | None = None
    config_signing_key_id: str | None = None
    config_signing_trusted_keys: dict[str, str] = field(default_factory=dict)

    def signing_keys(self) -> dict[str, str]:
        keys = dict(self.config_signing_trusted_keys)
        if self.config_signing_key_id and self.config_signing_public_key:
            keys.setdefault(self.config_signing_key_id, self.config_signing_public_key)
        return keys


class ConfigStore:
    def __init__(self, root: Path, protector: WindowsSecretProtector | None = None) -> None:
        self._identity_path = root / "config" / "agent-identity.json"
        self._config_path = root / "config" / "active-config.json"
        self._config_backup_path = root / "config" / "active-config.last-valid.json"
        self._protector = protector or WindowsSecretProtector()

    def load_identity(self) -> AgentIdentity | None:
        data = read_json(self._identity_path, None)
        if data is None:
            return None
        protected_token = data.pop("protected_agent_token", None)
        if isinstance(protected_token, str):
            scope = data.pop("secret_protection_scope", None)
            identity = AgentIdentity(agent_token=self._protector.unprotect(protected_token), **data)
            if scope != "machine":
                self.save_identity(identity)
            return identity
        identity = AgentIdentity(**data)
        self.save_identity(identity)
        return identity

    def save_identity(self, identity: AgentIdentity) -> None:
        data: dict[str, str] = {
            "agent_code": identity.agent_code,
            "protected_agent_token": self._protector.protect(identity.agent_token),
            "base_url": identity.base_url.rstrip("/"),
            "secret_protection_scope": "machine",
        }
        if identity.config_signing_public_key is not None:
            data["config_signing_public_key"] = identity.config_signing_public_key
        if identity.config_signing_key_id is not None:
            data["config_signing_key_id"] = identity.config_signing_key_id
        if identity.config_signing_trusted_keys:
            data["config_signing_trusted_keys"] = identity.config_signing_trusted_keys
        write_json_atomically(self._identity_path, data)

    def install_signing_trust(self, bundle: dict[str, object]) -> bool:
        """Pins a build-time public key without replacing the enrolled token."""
        identity = self.load_identity()
        if identity is None:
            raise RuntimeError("No existe una identidad enrolada para instalar la confianza de firma.")

        algorithm = bundle.get("algorithm")
        public_key = bundle.get("public_key")
        key_id = bundle.get("key_id")
        if algorithm != "ed25519":
            raise ValueError("El paquete de confianza no usa Ed25519.")
        if not isinstance(key_id, str) or re.fullmatch(r"[A-Za-z0-9._-]{1,100}", key_id) is None:
            raise ValueError("El identificador de la clave de firma es inválido.")
        if not isinstance(public_key, str):
            raise ValueError("La clave pública de firma es inválida.")
        try:
            decoded = b64decode(public_key, validate=True)
        except (Base64Error, ValueError) as exc:
            raise ValueError("La clave pública de firma no es base64 válido.") from exc
        if len(decoded) != 32:
            raise ValueError("La clave pública Ed25519 debe contener exactamente 32 bytes.")

        existing_keys = identity.signing_keys()
        if existing_keys:
            if existing_keys.get(key_id) == public_key:
                return False
            raise RuntimeError(
                "La identidad ya confía en otra clave. La rotación requiere un procedimiento explícito."
            )

        self.save_identity(replace(
            identity,
            config_signing_public_key=public_key,
            config_signing_key_id=key_id,
        ))
        return True

    def apply_signed_trust_update(
        self,
        update: dict[str, object],
        verified_by: str,
    ) -> bool:
        """Applies key additions/retirements only after the full config was verified."""
        identity = self.load_identity()
        if identity is None:
            raise RuntimeError("No existe una identidad enrolada.")
        keys = identity.signing_keys()
        if verified_by not in keys:
            raise ValueError("La transición no fue firmada por una clave confiable.")

        changed = False
        additions = update.get("add", [])
        retirements = update.get("retire", [])
        if not isinstance(additions, list) or not isinstance(retirements, list):
            raise ValueError("La transición del llavero es inválida.")

        for addition in additions:
            if not isinstance(addition, dict):
                raise ValueError("La clave agregada es inválida.")
            key_id, public_key = self._validated_signing_key(addition)
            existing = keys.get(key_id)
            if existing is not None and existing != public_key:
                raise ValueError("Una transición intentó redefinir un key_id existente.")
            if existing is None:
                keys[key_id] = public_key
                changed = True

        for key_id in retirements:
            if not isinstance(key_id, str) or key_id not in keys:
                raise ValueError("La transición intentó retirar una clave desconocida.")
            if key_id == verified_by:
                raise ValueError("Una transición no puede retirar la clave que la firma.")
            del keys[key_id]
            changed = True

        if not keys:
            raise ValueError("La transición no puede dejar el llavero vacío.")
        if changed:
            keep_legacy = identity.config_signing_key_id in keys
            self.save_identity(replace(
                identity,
                config_signing_public_key=identity.config_signing_public_key if keep_legacy else None,
                config_signing_key_id=identity.config_signing_key_id if keep_legacy else None,
                config_signing_trusted_keys=keys,
            ))
        return changed

    @staticmethod
    def _validated_signing_key(bundle: dict[str, object]) -> tuple[str, str]:
        if bundle.get("algorithm") != "ed25519":
            raise ValueError("El paquete de confianza no usa Ed25519.")
        public_key = bundle.get("public_key")
        key_id = bundle.get("key_id")
        if not isinstance(key_id, str) or re.fullmatch(r"[A-Za-z0-9._-]{1,100}", key_id) is None:
            raise ValueError("El identificador de la clave de firma es inválido.")
        if not isinstance(public_key, str):
            raise ValueError("La clave pública de firma es inválida.")
        try:
            decoded = b64decode(public_key, validate=True)
        except (Base64Error, ValueError) as exc:
            raise ValueError("La clave pública de firma no es base64 válido.") from exc
        if len(decoded) != 32:
            raise ValueError("La clave pública Ed25519 debe contener exactamente 32 bytes.")
        return key_id, public_key

    def load_active_config(self) -> dict[str, object] | None:
        data = self._load_config_with_fallback()
        if data is None:
            return None
        config = deepcopy(data)
        # This is storage-only metadata. It was never part of the configuration
        # signed by the Center and must not reach a later signature verification.
        secret_protection_scope = config.pop("_local_secret_protection_scope", None)
        target = self._bapps_mysql_target(config)
        if target is not None:
            protected_password = target.pop("protected_password", None)
            if isinstance(protected_password, str):
                target["password"] = self._protector.unprotect(protected_password)
                if secret_protection_scope != "machine":
                    self.save_active_config(config)
        self._restore_assignment_secrets(config)
        return config

    def save_active_config(self, config: dict[str, object]) -> None:
        stored = deepcopy(config)
        target = self._bapps_mysql_target(stored)
        if target is not None:
            password = target.pop("password", None)
            if isinstance(password, str):
                target["protected_password"] = self._protector.protect(password)
                stored["_local_secret_protection_scope"] = "machine"
        self._protect_assignment_secrets(stored)
        write_json_atomically(self._config_path, stored)
        write_json_atomically(self._config_backup_path, stored)

    def _load_config_with_fallback(self) -> dict[str, object] | None:
        primary = self._read_config_file(self._config_path)
        if primary is not None:
            return primary
        return self._read_config_file(self._config_backup_path)

    @staticmethod
    def _read_config_file(path: Path) -> dict[str, object] | None:
        try:
            data: Any = read_json(path, None)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _bapps_mysql_target(config: dict[str, object]) -> dict[str, object] | None:
        targets = config.get("targets")
        if not isinstance(targets, dict):
            return None
        target = targets.get("bapps_mysql")
        return target if isinstance(target, dict) else None

    def _protect_assignment_secrets(self, config: dict[str, object]) -> None:
        for secrets in self._assignment_secret_maps(config):
            token = secrets.pop("orders_api_token", None)
            if isinstance(token, str):
                secrets["protected_orders_api_token"] = self._protector.protect(token)
                config["_local_secret_protection_scope"] = "machine"

    def _restore_assignment_secrets(self, config: dict[str, object]) -> None:
        for secrets in self._assignment_secret_maps(config):
            protected = secrets.pop("protected_orders_api_token", None)
            if isinstance(protected, str):
                secrets["orders_api_token"] = self._protector.unprotect(protected)

    @staticmethod
    def _assignment_secret_maps(config: dict[str, object]) -> list[dict[str, object]]:
        found: list[dict[str, object]] = []
        syncs = config.get("syncs")
        if not isinstance(syncs, list):
            return found
        for assignment in syncs:
            if not isinstance(assignment, dict):
                continue
            sync_config = assignment.get("config")
            if not isinstance(sync_config, dict):
                continue
            secrets = sync_config.get("secrets")
            if isinstance(secrets, dict):
                found.append(secrets)
        return found
