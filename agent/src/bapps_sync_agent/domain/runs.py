from dataclasses import dataclass, field
from datetime import datetime
from threading import Event
from uuid import uuid4

from .errors import SyncInterrupted


@dataclass(slots=True)
class SyncContext:
    run_id: str
    correlation_id: str
    sync_code: str
    trigger: str
    stop_event: Event

    def raise_if_stopped(self) -> None:
        if self.stop_event.is_set():
            raise SyncInterrupted()


@dataclass(slots=True)
class ActiveRun:
    context: SyncContext
    started_at: datetime
    stop_event: Event = field(default_factory=Event)

    @classmethod
    def create(
        cls, sync_code: str, trigger: str, started_at: datetime, run_id: str | None = None
    ) -> "ActiveRun":
        stop_event = Event()
        return cls(
            context=SyncContext(
                run_id=run_id or f"RUN-{uuid4().hex}",
                correlation_id=f"CORR-{uuid4().hex}",
                sync_code=sync_code,
                trigger=trigger,
                stop_event=stop_event,
            ),
            started_at=started_at,
            stop_event=stop_event,
        )
