class SyncInterrupted(Exception):
    """Raised when a synchronizer observes a cooperative stop request."""


class SyncNotFound(Exception):
    """Raised when the requested sync code has no registered implementation."""


class SyncPaused(Exception):
    """Raised when policy disallows a run for a paused sync."""
