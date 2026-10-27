from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil

from bapps_sync_agent.application.runtime import create_agent_service


class BappsSyncService(win32serviceutil.ServiceFramework):
    """Runs the agent runtime under the Windows Service Control Manager."""

    _svc_name_ = "BAPPSyncAgent"
    _svc_display_name_ = "BAPPS Sync Agent"
    _svc_description_ = "Sincroniza fuentes locales con BAPPS Sync."
    _exe_name_ = sys.executable

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self._stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._runtime = None
        self._thread: threading.Thread | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._runtime is not None:
            self._runtime.stop()
        win32event.SetEvent(self._stop_event)

    def SvcDoRun(self) -> None:
        state_dir = Path(os.environ.get("BAPPS_SYNC_STATE_DIR", "C:/ProgramData/Bapps/SyncAgent"))
        servicemanager.LogInfoMsg("BAPPS Sync Agent service started")
        try:
            self._runtime = create_agent_service(state_dir)
            self._thread = threading.Thread(
                target=self._run_runtime,
                daemon=True,
                name="bapps-sync-service",
            )
            self._thread.start()
            win32event.WaitForSingleObject(self._stop_event, win32event.INFINITE)
        except Exception as exc:
            servicemanager.LogErrorMsg(f"BAPPS Sync Agent could not start: {exc}")
            raise
        finally:
            if self._runtime is not None:
                self._runtime.stop()
            if self._thread is not None:
                self._thread.join(timeout=30)
            servicemanager.LogInfoMsg("BAPPS Sync Agent service stopped")

    def _run_runtime(self) -> None:
        try:
            self._runtime.run_forever()
        except Exception as exc:
            servicemanager.LogErrorMsg(f"BAPPS Sync Agent runtime stopped unexpectedly: {exc}")
            win32event.SetEvent(self._stop_event)


def portable_self_test() -> None:
    """Verifies the bundled service dependencies without installing a service."""
    assert win32service.SERVICE_STOP_PENDING
    assert win32event.WAIT_OBJECT_0 == 0
    print("BAPPS Sync Service: self-test correcto.")


if __name__ == "__main__":
    if "--portable-self-test" in sys.argv:
        portable_self_test()
        raise SystemExit(0)
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(BappsSyncService)
        servicemanager.StartServiceCtrlDispatcher()
        raise SystemExit(0)
    raise SystemExit(win32serviceutil.HandleCommandLine(BappsSyncService))
