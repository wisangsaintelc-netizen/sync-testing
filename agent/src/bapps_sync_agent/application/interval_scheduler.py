class IntervalScheduler:
    """Monotonic local scheduler; each enabled sync first runs after its interval."""

    def __init__(self) -> None:
        self._plans: dict[str, tuple[int, float]] = {}

    def due_sync_codes(self, config: dict[str, object], now: float) -> list[str]:
        syncs = config.get("syncs")
        active: dict[str, int] = {}
        if isinstance(syncs, list):
            for sync in syncs:
                if not isinstance(sync, dict) or sync.get("status") != "enabled":
                    continue
                code = sync.get("code")
                if not isinstance(code, str) or not code:
                    continue
                try:
                    interval = max(60, min(86_400, int(sync.get("interval_seconds", 900))))
                except (TypeError, ValueError):
                    interval = 900
                active[code] = interval

        for code in set(self._plans) - set(active):
            self._plans.pop(code, None)

        due: list[str] = []
        for code, interval in active.items():
            plan = self._plans.get(code)
            if plan is None or plan[0] != interval:
                self._plans[code] = (interval, now + interval)
                continue
            if now >= plan[1]:
                due.append(code)
                self._plans[code] = (interval, now + interval)
        return due
