"""Ed25519 verification of the full configuration supplied by the Center."""

from __future__ import annotations

from base64 import b64decode
from copy import deepcopy
import json
from typing import Any, Mapping

from bapps_sync_agent.infrastructure.config_store import AgentIdentity


class ConfigSignatureError(ValueError):
    pass


def canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


class ConfigSignatureVerifier:
    """Allows unsigned legacy configuration but never an unsigned recipe engine."""

    def verify(self, configuration: Mapping[str, Any], identity: AgentIdentity | None) -> str | None:
        signature = configuration.get("config_signature")
        recipe_present = self._contains_declarative_recipe(configuration)
        if signature is None:
            if recipe_present or configuration.get("config_signing_trust_update") is not None:
                raise ConfigSignatureError("La receta declarativa requiere una configuración firmada por el Centro.")
            return None
        if identity is None or not identity.signing_keys():
            raise ConfigSignatureError("El agente no tiene la clave pública para verificar la configuración.")
        if not isinstance(signature, Mapping):
            raise ConfigSignatureError("La firma de configuración es inválida.")
        if signature.get("algorithm") != "ed25519":
            raise ConfigSignatureError("El algoritmo de firma de configuración no está permitido.")
        key_id = signature.get("key_id")
        if not isinstance(key_id, str) or key_id not in identity.signing_keys():
            raise ConfigSignatureError("La firma usa una clave que no pertenece al llavero confiable.")
        if configuration.get("agent_code") != identity.agent_code:
            raise ConfigSignatureError("La configuración firmada pertenece a otro agente.")
        raw_signature = signature.get("signature")
        if not isinstance(raw_signature, str):
            raise ConfigSignatureError("La firma de configuración no está codificada correctamente.")
        try:
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        except (ImportError, ModuleNotFoundError) as exc:
            raise ConfigSignatureError("Falta la dependencia cryptography para verificar la configuración firmada.") from exc
        try:
            public_key = b64decode(identity.signing_keys()[key_id], validate=True)
            signature_bytes = b64decode(raw_signature, validate=True)
            signed = deepcopy(dict(configuration))
            signed.pop("config_signature", None)
            Ed25519PublicKey.from_public_bytes(public_key).verify(signature_bytes, canonical_json(signed))
        except (ValueError, TypeError, InvalidSignature) as exc:
            raise ConfigSignatureError("La firma de configuración no es válida.") from exc
        return key_id

    @staticmethod
    def _contains_declarative_recipe(configuration: Mapping[str, Any]) -> bool:
        syncs = configuration.get("syncs")
        if not isinstance(syncs, list):
            return False
        for assignment in syncs:
            if not isinstance(assignment, Mapping):
                continue
            config = assignment.get("config")
            if not isinstance(config, Mapping):
                continue
            recipe = config.get("recipe", config)
            if isinstance(recipe, Mapping) and recipe.get("engine") == "declarative_table_reader":
                return True
        return False
