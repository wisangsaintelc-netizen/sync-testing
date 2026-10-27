from enum import StrEnum


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPING = "stopping"
    SUCCESS = "success"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    SKIPPED = "skipped"


class SyncStatus(StrEnum):
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"


class CommandType(StrEnum):
    RUN_NOW = "run_now"
    STOP_RUN = "stop_run"
    PAUSE_SYNC = "pause_sync"
    RESUME_SYNC = "resume_sync"
    REFRESH_CONFIG = "refresh_config"
    INSPECT_SOURCE_TABLE = "inspect_source_table"
