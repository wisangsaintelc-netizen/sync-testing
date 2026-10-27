import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from bapps_sync_agent.application.runtime import create_agent_service
from bapps_sync_agent.infrastructure.bootstrap_store import BootstrapError, BootstrapStore
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.enrollment_client import EnrollmentClient, EnrollmentError
from bapps_sync_agent.infrastructure.runtime_status_store import RuntimeStatusStore
from bapps_sync_agent.infrastructure.single_instance_lock import AgentAlreadyRunning
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig
from bapps_sync_agent.infrastructure.source_connection_tester import SourceConnectionTester


class AgentControlPanel(ttk.Frame):
    def __init__(self, root: tk.Tk, state_dir: Path) -> None:
        super().__init__(root, padding=20)
        self._root = root
        self._state_dir = state_dir
        self._config_store = ConfigStore(state_dir)
        self._bootstrap_store = BootstrapStore()
        self._runtime_status = RuntimeStatusStore(state_dir)
        self._source_store = SourceConfigStore(state_dir)
        self._tester = SourceConnectionTester()
        self._runtime: Any | None = None
        self._runtime_thread: threading.Thread | None = None
        self._status = tk.StringVar(value="Listo para configurar la fuente local.")
        self._profile = tk.StringVar(value="default")
        self._driver = tk.StringVar(value="firebird")
        self._host = tk.StringVar()
        self._port = tk.StringVar(value="3050")
        self._database = tk.StringVar()
        self._username = tk.StringVar()
        self._password = tk.StringVar()
        self._charset = tk.StringVar(value="iso8859_1")
        self._build()
        self.refresh()
        self._root.after(100, self._ensure_enrolled)
        self._root.after(2_000, self._refresh_runtime_status)

    def _build(self) -> None:
        self.grid(sticky="nsew")
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        center = ttk.LabelFrame(self, text="Centro BAPPS (solo lectura)", padding=12)
        center.grid(row=0, column=0, sticky="ew")
        center.columnconfigure(1, weight=1)
        self._center_url = self._read_only_row(center, 0, "URL", "No enrolado")
        self._agent_code = self._read_only_row(center, 1, "Agente", "No enrolado")
        self._center_status = self._read_only_row(center, 2, "Estado", "Esperando enrolamiento")
        self._last_heartbeat = self._read_only_row(center, 3, "Último heartbeat", "Sin comunicación")

        bapps = ttk.LabelFrame(self, text="MySQL BAPPS (administrado desde el panel)", padding=12)
        bapps.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        bapps.columnconfigure(1, weight=1)
        self._bapps_status = self._read_only_row(bapps, 0, "Configuración", "Aún no recibida del panel")
        self._bapps_host = self._read_only_row(bapps, 1, "Servidor", "—")
        self._bapps_database = self._read_only_row(bapps, 2, "Base", "—")
        self._bapps_username = self._read_only_row(bapps, 3, "Usuario", "—")
        self._bapps_received_at = self._read_only_row(bapps, 4, "Recibida", "—")

        source = ttk.LabelFrame(self, text="Base de datos a leer (configuración local)", padding=12)
        source.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        source.columnconfigure(1, weight=1)
        self._entry_row(source, 0, "Perfil local", self._profile)
        ttk.Label(source, text="Motor").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        driver = ttk.Combobox(source, textvariable=self._driver, values=("firebird", "sqlserver", "mysql"), state="readonly", width=18)
        driver.grid(row=1, column=1, sticky="ew", pady=4)
        driver.bind("<<ComboboxSelected>>", lambda _event: self._set_default_port())
        self._entry_row(source, 2, "Host o IP", self._host)
        self._entry_row(source, 3, "Puerto", self._port)
        self._entry_row(source, 4, "Base / alias", self._database)
        self._entry_row(source, 5, "Usuario", self._username)
        self._entry_row(source, 6, "Contraseña", self._password, show="•")

        self._entry_row(source, 7, "Codificación Firebird", self._charset)

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="e", pady=(14, 0))
        self._enrollment_button = ttk.Button(actions, text="Reintentar enrolamiento", command=self._ensure_enrolled)
        self._enrollment_button.grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Actualizar estado", command=self.refresh).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions, text="Guardar", command=self.save).grid(row=0, column=2, padx=(0, 8))
        self._test_button = ttk.Button(actions, text="Probar conexión", command=self.test_connection)
        self._test_button.grid(row=0, column=3)
        self._bapps_test_button = ttk.Button(actions, text="Probar MySQL BAPPS", command=self.test_bapps_connection)
        self._bapps_test_button.grid(row=0, column=4, padx=(8, 0))
        ttk.Label(self, textvariable=self._status, foreground="#14532d", wraplength=560).grid(row=4, column=0, sticky="w", pady=(14, 0))

    @staticmethod
    def _read_only_row(parent: ttk.LabelFrame, row: int, label: str, default: str) -> ttk.Label:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=3)
        value = ttk.Label(parent, text=default)
        value.grid(row=row, column=1, sticky="w", pady=3)
        return value

    @staticmethod
    def _entry_row(parent: ttk.LabelFrame, row: int, label: str, variable: tk.StringVar, show: str | None = None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
        ttk.Entry(parent, textvariable=variable, show=show).grid(row=row, column=1, sticky="ew", pady=4)

    def refresh(self) -> None:
        identity = self._config_store.load_identity()
        active_config = self._config_store.load_active_config() or {}
        runtime_status = self._runtime_status.load()
        self._center_url.configure(text=identity.base_url if identity else "No enrolado")
        self._agent_code.configure(text=identity.agent_code if identity else "No enrolado")
        self._center_status.configure(text=self._center_state(identity is not None, runtime_status.state, runtime_status.message))
        self._last_heartbeat.configure(text=runtime_status.last_heartbeat_at or "Sin comunicación")
        bapps_mysql = self._bapps_mysql_target(active_config)
        self._bapps_status.configure(text="Configuración recibida" if bapps_mysql else "Aún no recibida del panel")
        self._bapps_host.configure(text=f"{bapps_mysql['host']}:{bapps_mysql['port']}" if bapps_mysql else "—")
        self._bapps_database.configure(text=str(bapps_mysql.get("database", "—")) if bapps_mysql else "—")
        self._bapps_username.configure(text=str(bapps_mysql.get("username", "—")) if bapps_mysql else "—")
        self._bapps_received_at.configure(text=str(bapps_mysql.get("configured_at", "—")) if bapps_mysql else "—")
        profile_ref = self._profile.get().strip() or "default"
        try:
            source = self._source_store.load(profile_ref)
        except ValueError as exc:
            self._status.set(str(exc))
            source = None
        if source:
            self._driver.set(source.driver)
            self._host.set(source.host)
            self._port.set(str(source.port))
            self._database.set(source.database)
            self._username.set(source.username)
            self._password.set(source.password)
            self._charset.set(source.charset)
            self._status.set(f"Perfil local {profile_ref} cargado. Las credenciales están protegidas con Windows DPAPI.")

    def _refresh_runtime_status(self) -> None:
        """Keep connection and heartbeat information current without user action."""
        if not self.winfo_exists():
            return
        self.refresh()
        self._root.after(2_000, self._refresh_runtime_status)

    @staticmethod
    def _center_state(enrolled: bool, state: str, message: str) -> str:
        if not enrolled:
            return message if state == "offline" else "Esperando enrolamiento"
        if state == "online":
            return "Conectado"
        if state == "degraded":
            return f"Centro accesible; configuración rechazada: {message}"
        if state == "offline":
            return f"Sin conexión: {message}"
        return "Enrolado; iniciando conexión"

    def _ensure_enrolled(self) -> None:
        if self._config_store.load_identity() is not None:
            self._enrollment_button.configure(state="disabled")
            self._start_runtime()
            self.refresh()
            return
        try:
            bootstrap = self._bootstrap_store.load()
            if bootstrap is None:
                self._runtime_status.mark_error("No se encontró bootstrap.json junto al agente.")
                self.refresh()
                return
        except BootstrapError as exc:
            self._runtime_status.mark_error(str(exc))
            self.refresh()
            return

        self._enrollment_button.configure(state="disabled")
        self._status.set("Enrolando agente en el Centro BAPPS...")

        def enroll() -> None:
            try:
                identity = EnrollmentClient().enroll(bootstrap)
                self._config_store.save_identity(identity)
            except EnrollmentError as exc:
                self._root.after(0, lambda: self._finish_enrollment(False, str(exc)))
                return
            self._root.after(0, lambda: self._finish_enrollment(True, "Agente enrolado correctamente."))

        threading.Thread(target=enroll, daemon=True).start()

    def _finish_enrollment(self, ok: bool, message: str) -> None:
        if not ok:
            self._runtime_status.mark_error(message)
            self._enrollment_button.configure(state="normal")
            self._status.set(message)
            self.refresh()
            return
        self._status.set(message)
        self._enrollment_button.configure(state="disabled")
        self._start_runtime()
        self.refresh()

    def _start_runtime(self) -> None:
        if self._runtime_thread is not None and self._runtime_thread.is_alive():
            return
        try:
            self._runtime = create_agent_service(self._state_dir)
        except RuntimeError as exc:
            self._runtime_status.mark_error(str(exc))
            return

        def run() -> None:
            try:
                self._runtime.run_forever()
            except AgentAlreadyRunning:
                self._root.after(
                    0,
                    lambda: self._status.set(
                        "El servicio Windows está activo; esta ventana funciona como panel de consulta y configuración."
                    ),
                )
            except Exception as exc:
                self._runtime_status.mark_error(str(exc))

        self._runtime_thread = threading.Thread(target=run, daemon=True, name="bapps-sync-runtime")
        self._runtime_thread.start()

    def close(self) -> None:
        if self._runtime is not None:
            self._runtime.stop()
        self._root.destroy()

    def save(self) -> None:
        try:
            profile_ref = self._profile.get().strip() or "default"
            self._source_store.save(self._form_config(), profile_ref)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("BAPPS Sync Agent", str(exc), parent=self._root)
            return
        self._status.set(f"Configuración de la fuente guardada en el perfil {profile_ref}.")

    def test_connection(self) -> None:
        try:
            config = self._form_config()
        except ValueError as exc:
            messagebox.showerror("BAPPS Sync Agent", str(exc), parent=self._root)
            return
        self._test_button.configure(state="disabled")
        self._status.set("Probando conexión...")

        def run() -> None:
            result = self._tester.test(config)
            self._root.after(0, lambda: self._finish_test(result.ok, result.message))

        threading.Thread(target=run, daemon=True).start()

    def _finish_test(self, ok: bool, message: str) -> None:
        self._test_button.configure(state="normal")
        self._status.set(message)
        if not ok:
            messagebox.showwarning("Prueba de conexión", message, parent=self._root)

    def test_bapps_connection(self) -> None:
        target = self._bapps_mysql_target(self._config_store.load_active_config() or {})
        if target is None:
            messagebox.showinfo("MySQL BAPPS", "Aún no se recibió una configuración MySQL desde el Centro BAPPS.", parent=self._root)
            return
        try:
            config = SourceDatabaseConfig(
                driver="mysql",
                host=str(target["host"]),
                port=int(target["port"]),
                database=str(target["database"]),
                username=str(target["username"]),
                password=str(target["password"]),
            )
            config.validate()
        except (KeyError, TypeError, ValueError) as exc:
            messagebox.showerror("MySQL BAPPS", f"La configuración recibida es inválida: {exc}", parent=self._root)
            return
        self._bapps_test_button.configure(state="disabled")
        self._status.set("Probando conexión con MySQL BAPPS...")

        def run() -> None:
            result = self._tester.test(config)
            self._root.after(0, lambda: self._finish_bapps_test(result.ok, result.message))

        threading.Thread(target=run, daemon=True).start()

    def _finish_bapps_test(self, ok: bool, message: str) -> None:
        self._bapps_test_button.configure(state="normal")
        self._status.set(f"MySQL BAPPS: {message}")
        if not ok:
            messagebox.showwarning("Prueba MySQL BAPPS", message, parent=self._root)

    def _form_config(self) -> SourceDatabaseConfig:
        try:
            port = int(self._port.get())
        except ValueError as exc:
            raise ValueError("El puerto debe ser un número entero.") from exc
        config = SourceDatabaseConfig(
            driver=self._driver.get(), host=self._host.get(), port=port,
            database=self._database.get(), username=self._username.get(), password=self._password.get(),
            charset=self._charset.get(),
        )
        config.validate()
        return config

    def _set_default_port(self) -> None:
        default_ports = {"firebird": "3050", "sqlserver": "1433", "mysql": "3306"}
        self._port.set(default_ports[self._driver.get()])

    @staticmethod
    def _bapps_mysql_target(config: dict[str, object]) -> dict[str, object] | None:
        targets = config.get("targets")
        if not isinstance(targets, dict):
            return None
        target = targets.get("bapps_mysql")
        return target if isinstance(target, dict) else None


def launch_control_panel(state_dir: Path) -> None:
    root = tk.Tk()
    root.title("BAPPS Sync Agent")
    root.minsize(700, 740)
    panel = AgentControlPanel(root, state_dir)
    root.protocol("WM_DELETE_WINDOW", panel.close)
    root.mainloop()
