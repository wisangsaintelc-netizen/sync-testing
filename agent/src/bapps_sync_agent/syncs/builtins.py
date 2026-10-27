from pathlib import Path
from typing import Any, Mapping

from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore
from bapps_sync_agent.syncs.clientes_valery import ClientesValerySynchronizer
from bapps_sync_agent.syncs.declarative_table_reader import DeclarativeTableReaderSynchronizer
from bapps_sync_agent.syncs.registry import SynchronizerRegistry
from bapps_sync_agent.syncs.valery_prs_writer import ValeryPrsWriterSynchronizer


def create_builtin_synchronizer_registry(
    state_dir: Path, config_store: ConfigStore
) -> SynchronizerRegistry:
    """Register the synchronizers shipped with the agent in one explicit place."""
    declarative_reader = DeclarativeTableReaderSynchronizer(SourceConfigStore(state_dir), config_store)
    prs_writer = ValeryPrsWriterSynchronizer(SourceConfigStore(state_dir), config_store)

    def recipe_synchronizer(sync_code: str):
        active_config = config_store.load_active_config() or {}
        syncs = active_config.get("syncs")
        if not isinstance(syncs, list):
            return None
        for assignment in syncs:
            if not isinstance(assignment, Mapping) or assignment.get("code") != sync_code:
                continue
            config: Any = assignment.get("config")
            if not isinstance(config, Mapping):
                return None
            recipe: Any = config.get("recipe", config)
            if not isinstance(recipe, Mapping):
                return None
            if recipe.get("engine") == "declarative_table_reader":
                return declarative_reader
            if recipe.get("engine") == ValeryPrsWriterSynchronizer.ENGINE:
                return prs_writer
            return None
        return None

    return SynchronizerRegistry({
        ClientesValerySynchronizer.CODE: ClientesValerySynchronizer(
            SourceConfigStore(state_dir), config_store
        ),
    }, fallback=recipe_synchronizer)
