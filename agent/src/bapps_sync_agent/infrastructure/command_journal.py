from datetime import UTC, datetime
from pathlib import Path

from .atomic_json import read_json, write_json_atomically


class CommandJournal:
    def __init__(self, root: Path, max_entries: int = 10_000) -> None:
        self._path = root / "state" / "command-journal.json"
        self._max_entries = max_entries

    def get(self, command_id: str) -> dict[str, object] | None:
        return read_json(self._path, {}).get(command_id)

    def record(self, command_id: str, status: str, result: dict[str, object] | None = None) -> None:
        entries: dict[str, dict[str, object]] = read_json(self._path, {})
        entries[command_id] = {
            "status": status,
            "result": result or {},
            "completed_at": datetime.now(UTC).isoformat(),
        }
        if len(entries) > self._max_entries:
            oldest = sorted(entries, key=lambda key: str(entries[key].get("completed_at", "")))[: len(entries) - self._max_entries]
            for key in oldest:
                entries.pop(key, None)
        write_json_atomically(self._path, entries)
