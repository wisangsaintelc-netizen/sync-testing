import json
from base64 import b64encode
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from random import Random

from bapps_sync_agent.infrastructure.command_journal import CommandJournal
from bapps_sync_agent.infrastructure.config_store import AgentIdentity, ConfigStore
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.infrastructure.run_state_store import RunStateStore
from bapps_sync_agent.infrastructure.single_instance_lock import AgentAlreadyRunning, SingleInstanceLock


class FakeProtector:
    def protect(self, value: str) -> str:
        return f"protected:{value[::-1]}"

    def unprotect(self, value: str) -> str:
        return value.removeprefix("protected:")[::-1]


class LocalStateTest(unittest.TestCase):
    def test_signing_trust_is_added_without_replacing_the_enrolled_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root, protector=FakeProtector())
            store.save_identity(AgentIdentity("AGT-1", "agent-secret", "https://center.test"))
            public_key = b64encode(b"k" * 32).decode("ascii")

            changed = store.install_signing_trust({
                "algorithm": "ed25519",
                "key_id": "recipe-v1",
                "public_key": public_key,
            })

            identity = store.load_identity()
            self.assertTrue(changed)
            self.assertEqual(identity.agent_token, "agent-secret")
            self.assertEqual(identity.config_signing_public_key, public_key)
            self.assertEqual(identity.config_signing_key_id, "recipe-v1")

    def test_signing_trust_never_silently_replaces_a_pinned_key(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = ConfigStore(Path(temporary), protector=FakeProtector())
            store.save_identity(AgentIdentity(
                "AGT-1", "agent-secret", "https://center.test",
                b64encode(b"a" * 32).decode("ascii"), "recipe-v1",
            ))

            with self.assertRaisesRegex(RuntimeError, "rotación"):
                store.install_signing_trust({
                    "algorithm": "ed25519",
                    "key_id": "recipe-v2",
                    "public_key": b64encode(b"b" * 32).decode("ascii"),
                })

    def test_signed_transition_adds_and_then_retires_keys_without_reinstall(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = ConfigStore(Path(temporary), protector=FakeProtector())
            first = b64encode(b"a" * 32).decode("ascii")
            second = b64encode(b"b" * 32).decode("ascii")
            store.save_identity(AgentIdentity(
                "AGT-1", "agent-secret", "https://center.test", first, "recipe-v1",
            ))

            self.assertTrue(store.apply_signed_trust_update({
                "add": [{"algorithm": "ed25519", "key_id": "recipe-v2", "public_key": second}],
                "retire": [],
            }, verified_by="recipe-v1"))
            self.assertEqual(store.load_identity().signing_keys(), {
                "recipe-v1": first,
                "recipe-v2": second,
            })

            self.assertTrue(store.apply_signed_trust_update({
                "add": [],
                "retire": ["recipe-v1"],
            }, verified_by="recipe-v2"))
            self.assertEqual(store.load_identity().signing_keys(), {"recipe-v2": second})

    def test_signed_transition_cannot_retire_its_own_signer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = ConfigStore(Path(temporary), protector=FakeProtector())
            store.save_identity(AgentIdentity(
                "AGT-1", "agent-secret", "https://center.test",
                b64encode(b"a" * 32).decode("ascii"), "recipe-v1",
            ))

            with self.assertRaisesRegex(ValueError, "firma"):
                store.apply_signed_trust_update({
                    "add": [],
                    "retire": ["recipe-v1"],
                }, verified_by="recipe-v1")

    def test_identity_and_command_journal_survive_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root, protector=FakeProtector())
            store.save_identity(AgentIdentity("AGT-1", "token", "https://center.test"))
            CommandJournal(root).record("CMD-1", "completed", {"run_id": "RUN-1"})

            self.assertEqual(store.load_identity().agent_code, "AGT-1")
            self.assertNotIn("\"token\"", (root / "config" / "agent-identity.json").read_text(encoding="utf-8"))
            self.assertIn('"secret_protection_scope":"machine"', (root / "config" / "agent-identity.json").read_text(encoding="utf-8"))
            self.assertEqual(CommandJournal(root).get("CMD-1")["result"]["run_id"], "RUN-1")

    def test_legacy_identity_is_migrated_to_protected_storage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "config" / "agent-identity.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                '{"agent_code":"AGT-1","agent_token":"legacy-token","base_url":"https://center.test"}',
                encoding="utf-8",
            )
            store = ConfigStore(root, protector=FakeProtector())

            self.assertEqual(store.load_identity().agent_token, "legacy-token")
            migrated = path.read_text(encoding="utf-8")
            self.assertNotIn("legacy-token", migrated)
            self.assertIn("protected_agent_token", migrated)
            self.assertIn('"secret_protection_scope":"machine"', migrated)

    def test_bapps_mysql_password_is_protected_at_rest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root, protector=FakeProtector())
            store.save_active_config({
                "schema_version": "1.1",
                "targets": {"bapps_mysql": {
                    "host": "mysql.bapps.test", "port": 3306, "database": "bapps",
                    "username": "sync", "password": "mysql-secret",
                }},
            })

            stored = (root / "config" / "active-config.json").read_text(encoding="utf-8")
            self.assertNotIn("mysql-secret", stored)
            self.assertIn('"_local_secret_protection_scope":"machine"', stored)
            loaded = store.load_active_config()
            self.assertNotIn("_local_secret_protection_scope", loaded)
            target = loaded["targets"]["bapps_mysql"]
            self.assertEqual(target["password"], "mysql-secret")

    def test_orders_api_token_is_protected_at_rest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root, protector=FakeProtector())
            store.save_active_config({
                "version": 8,
                "syncs": [{
                    "code": "valery_prs",
                    "config": {"secrets": {"orders_api_token": "orders-secret-token"}},
                }],
            })

            stored = (root / "config" / "active-config.json").read_text(encoding="utf-8")
            self.assertNotIn("orders-secret-token", stored)
            self.assertIn("protected_orders_api_token", stored)
            loaded = store.load_active_config()
            self.assertEqual(
                loaded["syncs"][0]["config"]["secrets"]["orders_api_token"],
                "orders-secret-token",
            )

    def test_existing_mysql_secret_is_migrated_to_machine_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "config" / "active-config.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                "schema_version": "1.1",
                "targets": {"bapps_mysql": {
                    "host": "mysql.bapps.test", "port": 3306, "database": "bapps",
                    "username": "sync", "protected_password": "protected:terces-lqsym",
                }},
            }), encoding="utf-8")

            config = ConfigStore(root, protector=FakeProtector()).load_active_config()

            self.assertEqual(config["targets"]["bapps_mysql"]["password"], "mysql-secret")
            self.assertIn('"_local_secret_protection_scope":"machine"', path.read_text(encoding="utf-8"))

    def test_corrupt_active_config_falls_back_to_the_last_valid_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = ConfigStore(root, protector=FakeProtector())
            store.save_active_config({"version": 7, "syncs": [{"code": "clientes_valery", "status": "enabled"}]})
            (root / "config" / "active-config.json").write_text("{not valid json", encoding="utf-8")

            config = store.load_active_config()

            self.assertEqual(config["version"], 7)
            self.assertEqual(config["syncs"][0]["code"], "clientes_valery")

    def test_outbox_recovers_sending_items_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary))
            outbox.persist({"event_type": "run_started"})
            sending = outbox.claim(outbox.pending()[0])
            self.assertTrue(sending.exists())
            outbox.recover_sending()
            self.assertEqual(len(outbox.pending()), 1)

    def test_outbox_defers_retry_until_its_persisted_backoff_expires(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outbox = Outbox(Path(temporary), random_source=Random(0))
            outbox.persist({"event_type": "run_started"})
            sending = outbox.claim(outbox.pending()[0])
            now = datetime(2026, 7, 17, tzinfo=UTC)
            outbox.retry(sending, now=now)

            self.assertEqual(outbox.pending(now=now), [])
            self.assertEqual(len(outbox.pending(now=now + timedelta(seconds=2))), 1)
            self.assertEqual(outbox.backlog_stats()[0], 1)

    def test_run_state_retains_only_unfinished_runs_for_crash_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = RunStateStore(Path(temporary))
            store.mark_started({
                "run_id": "RUN-1",
                "correlation_id": "CORR-1",
                "sync_code": "clientes_valery",
                "trigger": "command",
                "started_at": "2026-07-17T12:00:00+00:00",
            })
            store.mark_started({
                "run_id": "RUN-2",
                "correlation_id": "CORR-2",
                "sync_code": "clientes_valery",
                "trigger": "schedule",
                "started_at": "2026-07-17T12:01:00+00:00",
            })
            store.mark_finished("RUN-1")

            interrupted = store.recover_interrupted()
            self.assertEqual([run["run_id"] for run in interrupted], ["RUN-2"])
            self.assertEqual(store.recover_interrupted(), [])

    def test_single_instance_lock_rejects_second_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            first = SingleInstanceLock(Path(temporary))
            first.acquire()
            with self.assertRaises(AgentAlreadyRunning):
                SingleInstanceLock(Path(temporary)).acquire()
            first.release()
