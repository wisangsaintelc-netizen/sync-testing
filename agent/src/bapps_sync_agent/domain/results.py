from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class SyncResult:
    rows_read: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_deleted: int = 0
    rows_failed: int = 0
    error_code: str | None = None
    error_message: str | None = None

    def as_payload(self, duration_ms: int, status: str, trigger: str) -> dict[str, object]:
        return {**asdict(self), "duration_ms": duration_ms, "status": status, "trigger": trigger}
