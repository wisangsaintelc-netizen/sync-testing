import base64
import copy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bapps_sync_agent.infrastructure.config_signature import ConfigSignatureError, ConfigSignatureVerifier, canonical_json
from bapps_sync_agent.infrastructure.config_store import AgentIdentity, ConfigStore


class FakeProtector:
    def protect(self, value: str) -> str:
        return f"protected:{value[::-1]}"

    def unprotect(self, value: str) -> str:
        return value.removeprefix("protected:")[::-1]


def signed_recipe_config(with_mysql_target: bool = False) -> tuple[dict[str, object], AgentIdentity]:
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    identity = AgentIdentity("AGT-PROFIT-01", "token", "https://center.test", base64.b64encode(public_key).decode(), "recipe-v1")
    config: dict[str, object] = {
        "schema_version": "1.1",
        "version": 1,
        "agent_code": "AGT-PROFIT-01",
        "syncs": [{"code": "profit_factura", "config": {"recipe": {"engine": "declarative_table_reader"}}}],
    }
    if with_mysql_target:
        config["targets"] = {"bapps_mysql": {
            "host": "mysql.test", "port": 3306, "database": "bapps",
            "username": "sync", "password": "mysql-secret",
        }}
    config["config_signature"] = {
        "algorithm": "ed25519",
        "key_id": "recipe-v1",
        "signature": base64.b64encode(private_key.sign(canonical_json(config))).decode(),
    }
    return config, identity


class ConfigSignatureTest(unittest.TestCase):
    def test_accepts_a_valid_agent_bound_ed25519_configuration(self) -> None:
        config, identity = signed_recipe_config()

        verified_by = ConfigSignatureVerifier().verify(config, identity)

        self.assertEqual(verified_by, "recipe-v1")

    def test_accepts_a_signature_from_a_second_trusted_key(self) -> None:
        config, identity = signed_recipe_config()
        next_private = Ed25519PrivateKey.generate()
        next_public = base64.b64encode(
            next_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        ).decode()
        identity = AgentIdentity(
            identity.agent_code, identity.agent_token, identity.base_url,
            identity.config_signing_public_key, identity.config_signing_key_id,
            {"recipe-v2": next_public},
        )
        config.pop("config_signature")
        config["config_signature"] = {
            "algorithm": "ed25519",
            "key_id": "recipe-v2",
            "signature": base64.b64encode(next_private.sign(canonical_json(config))).decode(),
        }

        self.assertEqual(ConfigSignatureVerifier().verify(config, identity), "recipe-v2")

    def test_rejects_tampering_after_the_center_signature(self) -> None:
        config, identity = signed_recipe_config()
        tampered = copy.deepcopy(config)
        tampered["version"] = 2

        with self.assertRaises(ConfigSignatureError):
            ConfigSignatureVerifier().verify(tampered, identity)

    def test_local_mysql_secret_metadata_does_not_invalidate_the_center_signature(self) -> None:
        config, identity = signed_recipe_config(with_mysql_target=True)
        with TemporaryDirectory() as temporary:
            store = ConfigStore(Path(temporary), protector=FakeProtector())
            store.save_active_config(config)

            loaded = store.load_active_config()

        self.assertNotIn("_local_secret_protection_scope", loaded)
        self.assertEqual(ConfigSignatureVerifier().verify(loaded, identity), "recipe-v1")

    def test_legacy_config_without_a_recipe_remains_compatible(self) -> None:
        ConfigSignatureVerifier().verify({"agent_code": "AGT-LEGACY", "syncs": []}, None)

    def test_unsigned_trust_update_is_never_accepted(self) -> None:
        with self.assertRaises(ConfigSignatureError):
            ConfigSignatureVerifier().verify({
                "agent_code": "AGT-LEGACY",
                "syncs": [],
                "config_signing_trust_update": {"add": [], "retire": []},
            }, None)
