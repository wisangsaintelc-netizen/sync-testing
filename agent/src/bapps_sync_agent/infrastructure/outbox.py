import json
import os
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .atomic_json import read_json, write_json_atomically


class Outbox:
    """File-backed at-least-once event queue with durable retry scheduling."""

    def __init__(self, root: Path, random_source: random.Random | None = None) -> None:
        self._root = root / "outbox"
        self._retry_path = self._root / "retry-state.json"
        self._random = random_source or random.Random()
        for state in ("pending", "sending", "failed"):
            (self._root / state).mkdir(parents=True, exist_ok=True)

    def persist(self, event: dict[str, object]) -> str:
        event_id = str(event.get("event_id") or f"EVT-{uuid4().hex}")
        event["event_id"] = event_id
        temporary = self._root / "pending" / f".{event_id}.tmp"
        target = self._root / "pending" / f"{event_id}.json"
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(event, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        return event_id

    def recover_sending(self) -> None:
        for path in (self._root / "sending").glob("*.json"):
            os.replace(path, self._root / "pending" / path.name)

    def pending(self, now: datetime | None = None) -> list[Path]:
        current = now or datetime.now(UTC)
        retry_state = self._retry_state()
        paths = sorted((self._root / "pending").glob("*.json"))
        return [path for path in paths if self._is_due(path, retry_state, current)]

    def backlog_stats(self) -> tuple[int, int]:
        paths = list((self._root / "pending").glob("*.json")) + list((self._root / "sending").glob("*.json"))
        return len(paths), sum(path.stat().st_size for path in paths)

    def claim(self, path: Path) -> Path:
        target = self._root / "sending" / path.name
        os.replace(path, target)
        return target

    def acknowledge(self, path: Path) -> None:
        self._clear_retry(path.stem)
        path.unlink(missing_ok=True)

    def retry(self, path: Path, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        retry_state = self._retry_state()
        previous = retry_state.get(path.stem, {})
        attempts = int(previous.get("attempts", 0)) + 1
        # 1, 2, 4 … seconds, capped at five minutes, with bounded positive jitter.
        delay_seconds = min(300.0, float(2 ** min(attempts - 1, 8))) + self._random.uniform(0.0, 1.0)
        retry_state[path.stem] = {
            "attempts": attempts,
            "next_attempt_at": (current + timedelta(seconds=delay_seconds)).isoformat(),
        }
        self._save_retry_state(retry_state)
        os.replace(path, self._root / "pending" / path.name)

    def fail(self, path: Path) -> None:
        self._clear_retry(path.stem)
        os.replace(path, self._root / "failed" / path.name)

    @staticmethod
    def read(path: Path) -> dict[str, object]:
        with path.open("r", encoding="utf-8") as handle:
            value: Any = json.load(handle)
        if not isinstance(value, dict):
            raise ValueError("Outbox event must be a JSON object")
        return value

    def _is_due(self, path: Path, retry_state: dict[str, dict[str, object]], now: datetime) -> bool:
        next_attempt = retry_state.get(path.stem, {}).get("next_attempt_at")
        if not isinstance(next_attempt, str):
            return True
        try:
            return datetime.fromisoformat(next_attempt).astimezone(UTC) <= now
        except ValueError:
            return True

    def _retry_state(self) -> dict[str, dict[str, object]]:
        value: Any = read_json(self._retry_path, {})
        if not isinstance(value, dict):
            return {}
        return {str(key): data for key, data in value.items() if isinstance(data, dict)}

    def _save_retry_state(self, state: dict[str, dict[str, object]]) -> None:
        write_json_atomically(self._retry_path, state)

    def _clear_retry(self, event_id: str) -> None:
        retry_state = self._retry_state()
        if event_id in retry_state:
            retry_state.pop(event_id)
            self._save_retry_state(retry_state)
