from collections.abc import Callable

from bapps_sync_agent.domain.errors import SyncNotFound
from bapps_sync_agent.syncs.protocol import Synchronizer


class SynchronizerRegistry:
    def __init__(
        self,
        synchronizers: dict[str, Synchronizer],
        fallback: Callable[[str], Synchronizer | None] | None = None,
    ) -> None:
        self._synchronizers = synchronizers
        self._fallback = fallback

    def resolve(self, sync_code: str) -> Synchronizer:
        try:
            return self._synchronizers[sync_code]
        except KeyError as exc:
            synchronizer = self._fallback(sync_code) if self._fallback is not None else None
            if synchronizer is not None:
                return synchronizer
            raise SyncNotFound(sync_code) from exc
