from typing import Protocol

from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.domain.runs import SyncContext


class Synchronizer(Protocol):
    def run(self, context: SyncContext) -> SyncResult: ...
