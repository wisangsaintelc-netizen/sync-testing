import argparse
import json
import sys
from pathlib import Path

from bapps_sync_agent.ui.app import launch_control_panel
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore
from bapps_sync_agent.infrastructure.state_permissions import repair_state_permissions


def portable_self_test() -> None:
    """Exercise database and signature imports loaded dynamically in a frozen build."""
    import firebirdsql
    import pyodbc
    import pymysql
    import tkinter
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from firebirdsql.wireprotocol import get_crypt

    if not firebirdsql.__version__:
        raise RuntimeError("firebirdsql version is unavailable")
    if not pymysql.__version__:
        raise RuntimeError("PyMySQL version is unavailable")
    if not pyodbc.version:
        raise RuntimeError("pyodbc version is unavailable")
    if not Ed25519PrivateKey.generate():
        raise RuntimeError("Ed25519 support is unavailable")
    if not get_crypt("bapps-sync-portable-test"):
        raise RuntimeError("Legacy_Auth password hashing is unavailable")
    if getattr(sys, "frozen", False):
        interpreter = tkinter.Tcl()
        if interpreter.eval("expr {6 * 7}") != "42":
            raise RuntimeError("Tcl/Tk runtime is unavailable")


def prepare_service(state_dir: Path) -> None:
    """Migrates local DPAPI data before the service runs as LocalSystem."""
    config_store = ConfigStore(state_dir)
    if config_store.load_identity() is None:
        raise RuntimeError("El agente debe enrolarse antes de instalar el servicio.")
    config_store.load_active_config()
    SourceConfigStore(state_dir).load()


def install_signing_trust(state_dir: Path, bundle_path: Path) -> None:
    try:
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("No se pudo leer el paquete de confianza de firma.") from exc
    if not isinstance(bundle, dict):
        raise RuntimeError("El paquete de confianza de firma debe ser un objeto JSON.")
    store = ConfigStore(state_dir)
    if store.load_identity() is None:
        print("La confianza se instalará mediante el enrolamiento inicial.")
        return
    changed = store.install_signing_trust(bundle)
    print("Confianza de firma instalada." if changed else "La confianza de firma ya estaba instalada.")


def main() -> None:
    parser = argparse.ArgumentParser(description="BAPPS Sync Agent control panel")
    parser.add_argument("--state-dir", type=Path, default=Path("C:/ProgramData/Bapps/SyncAgent"))
    parser.add_argument("--portable-self-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prepare-service", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--repair-state-permissions", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--install-signing-trust", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.portable_self_test:
        portable_self_test()
        return
    if args.prepare_service:
        prepare_service(args.state_dir)
        return
    if args.repair_state_permissions:
        repair_state_permissions(args.state_dir)
        return
    if args.install_signing_trust:
        install_signing_trust(args.state_dir, args.install_signing_trust)
        return
    launch_control_panel(args.state_dir)


if __name__ == "__main__":
    main()
