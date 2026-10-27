import argparse
from pathlib import Path

from bapps_sync_agent.application.runtime import create_agent_service
from bapps_sync_agent.infrastructure.config_store import ConfigStore


def main() -> None:
    parser = argparse.ArgumentParser(description="BAPPS Sync Agent")
    parser.add_argument("--state-dir", type=Path, default=Path("C:/ProgramData/Bapps/SyncAgent"))
    parser.add_argument("--gui", action="store_true", help="Open the local read-only status and source configuration panel.")
    args = parser.parse_args()

    if args.gui:
        from bapps_sync_agent.ui.app import launch_control_panel

        launch_control_panel(args.state_dir)
        return

    if ConfigStore(args.state_dir).load_identity() is None:
        raise SystemExit("Agent identity missing. Enroll the agent before starting the service.")
    create_agent_service(args.state_dir).run_forever()


if __name__ == "__main__":
    main()
