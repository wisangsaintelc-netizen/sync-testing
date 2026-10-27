from pathlib import Path

from bapps_sync_agent.application.agent_service import AgentService
from bapps_sync_agent.application.sync_runner import SyncRunner
from bapps_sync_agent.infrastructure.api_client import ApiClient
from bapps_sync_agent.infrastructure.command_journal import CommandJournal
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.local_sync_log import LocalSyncLogRepository
from bapps_sync_agent.infrastructure.outbox import Outbox
from bapps_sync_agent.infrastructure.run_state_store import RunStateStore
from bapps_sync_agent.infrastructure.runtime_status_store import RuntimeStatusStore
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore
from bapps_sync_agent.infrastructure.source_table_inspector import SourceTableInspector
from bapps_sync_agent.syncs.builtins import create_builtin_synchronizer_registry


def create_agent_service(state_dir: Path) -> AgentService:
    config_store = ConfigStore(state_dir)
    identity = config_store.load_identity()
    if identity is None:
        raise RuntimeError("El agente debe estar enrolado antes de iniciar el runtime.")

    def is_enabled(sync_code: str) -> bool:
        config = config_store.load_active_config() or {}
        return any(sync.get("code") == sync_code and sync.get("status") == "enabled" for sync in config.get("syncs", []))

    outbox = Outbox(state_dir)
    run_state = RunStateStore(state_dir)
    registry = create_builtin_synchronizer_registry(state_dir, config_store)
    source_inspector = SourceTableInspector(SourceConfigStore(state_dir))
    return AgentService(
        root=state_dir,
        api_client=ApiClient(identity),
        config_store=config_store,
        outbox=outbox,
        runner=SyncRunner(
            registry=registry,
            outbox=outbox,
            is_enabled=is_enabled,
            run_state=run_state,
            local_log=LocalSyncLogRepository(config_store),
        ),
        journal=CommandJournal(state_dir),
        run_state=run_state,
        runtime_status=RuntimeStatusStore(state_dir),
        inspect_source_table=source_inspector.inspect,
    )
