from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .atomic_json import read_json, write_json_atomically


class RunStateStore:
    """Persists only runs that have started but have not reached a terminal state."""

    def __init__(self, root: Path) -> None:
        self._path = root / "state" / "last-run-state.json"

    def mark_started(self, run: dict[str, str]) -> None:
        runs = self._load()
        runs[run["run_id"]] = run
        self._save(runs)

    def mark_finished(self, run_id: str) -> None:
        runs = self._load()
        if run_id in runs:
            runs.pop(run_id)
            self._save(runs)

    def recover_interrupted(self) -> list[dict[str, str]]:
        runs = list(self._load().values())
        write_json_atomically(self._path, {"active_runs": {}})
        return runs

    def _load(self) -> dict[str, dict[str, str]]:
        data: Any = read_json(self._path, {"active_runs": {}})
        active_runs = data.get("active_runs", {}) if isinstance(data, dict) else {}
        if not isinstance(active_runs, dict):
            raise ValueError("Invalid last-run state")
        return {
            str(run_id): {str(key): str(value) for key, value in run.items()}
            for run_id, run in active_runs.items()
            if isinstance(run, dict)
        }

    def _save(self, runs: Iterable[tuple[str, dict[str, str]]] | dict[str, dict[str, str]]) -> None:
        write_json_atomically(self._path, {"active_runs": dict(runs)})
