import os
from pathlib import Path
from typing import TextIO


class AgentAlreadyRunning(RuntimeError):
    pass


class SingleInstanceLock:
    """OS-backed lock; an orphaned lock file is harmless after a process crash."""

    def __init__(self, root: Path) -> None:
        self._path = root / "locks" / "agent.lock"
        self._handle: TextIO | None = None

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle = self._path.open("a+", encoding="utf-8")
        try:
            # `msvcrt.locking` locks a byte range, so make byte zero exist
            # before attempting the non-blocking lock on a new file.
            if self._path.stat().st_size == 0:
                handle.write("0")
                handle.flush()
            self._lock(handle)
        except OSError as exc:
            handle.close()
            raise AgentAlreadyRunning("BAPPS Sync Agent already running") from exc

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()))
        handle.flush()
        self._handle = handle

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._unlock(self._handle)
        finally:
            self._handle.close()
            self._handle = None
            self._path.unlink(missing_ok=True)

    @staticmethod
    def _lock(handle: TextIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _unlock(handle: TextIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
