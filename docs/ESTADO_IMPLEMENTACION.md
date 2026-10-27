# Estado de implementación — BAPPS Sync

**Corte:** 17 de julio de 2026.  
**Propósito:** fuente breve y verificable del avance del repositorio. Este documento distingue lo entregado de lo que solo está en progreso; no sustituye el diseño v1.1 ni sus contratos.

## Prueba local reproducible

## Última verificación (2026-07-17)

- Laravel: Pint correcto; 12 pruebas y 70 aserciones correctas.
- Núcleo del agente Python: 7 pruebas unitarias correctas.
- HTTP local: AGT-DEMO enrolado, heartbeat reconocido, clientes_valery recibido en configuración y CMD-DEMO-RUN-NOW reclamado.

Este es el conteo vigente de verificación y sustituye referencias de conteos anteriores.

La guía [GUIA_PRUEBA_VERTICAL.md](GUIA_PRUEBA_VERTICAL.md) contiene el recorrido local de enrolamiento, `heartbeat`, configuración y reclamación de comandos. El comando `php artisan bapps:demo-provision --with-command` prepara los datos de demostración sin requerir Tinker.

## Resumen

| Área | Estado | Alcance comprobable |
|---|---|---|
| Frontend React | Terminado con mocks | SPA, contratos tipados, MSW y vistas operativas contra datos simulados. |
| API de agentes Laravel | Implementada | Enrolamiento, heartbeat, configuración, comandos y eventos, con autenticación por agente e idempotencia en los casos cubiertos. |
| Núcleo del agente Python (F1–F2) | Implementado | Estado local durable, outbox, journal, exclusión de instancia, bucle de control, cliente HTTP y runner de un único worker. |
| API de control Laravel (lectura) | Implementada | Login y consultas de dashboard, agentes y ejecuciones disponibles; las mutaciones siguen pendientes. |

## 1. Frontend React — terminado con mocks

La SPA está integrada en Laravel con React, TypeScript y Vite. La evidencia de la implementación y su corte funcional está en [ONGOING.txt](ONGOING.txt), y el alcance original en [PLAN_IMPLEMENTACION_FRONTEND_v1.0.md](PLAN_IMPLEMENTACION_FRONTEND_v1.0.md).

El contrato ejecutable que consume la SPA está en:

- `resources/js/api/types.ts`
- `resources/js/api/endpoints.ts`
- `resources/js/mocks/handlers.ts`

Los mocks MSW son, por ahora, la fuente de las respuestas de control. Por tanto, las vistas no están conectadas aún a una API Laravel de operadores ni a datos producidos por un agente real.

## 2. API de agentes Laravel — implementada

Las rutas agente↔centro están definidas en `routes/api.php` bajo `/api/v1/agent`:

- `POST /enroll`
- `POST /heartbeat`
- `GET /config`
- `POST /commands/claim`
- `POST /commands/{commandId}/result`
- `POST /events`

La implementación se concentra en `app/Http/Controllers/AgentApi`, `app/Actions/AgentApi`, `app/Http/Requests/AgentApi` y los modelos de `app/Models`. El esquema central está en `database/migrations/2026_07_17_120000_create_bapps_sync_tables.php`.

La prueba de integración disponible es `tests/Feature/AgentApiTest.php`. Cubre enrolamiento y rotación de credencial, configuración versionada por agente, claim de comandos con alcance/idempotencia y eventos idempotentes sin cruce entre agentes.

El diseño de referencia para estos endpoints permanece en [03_CENTRO_LARAVEL_Y_API.md](backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/03_CENTRO_LARAVEL_Y_API.md), [04_CONTRATOS_Y_MAQUINAS_DE_ESTADO.md](backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/04_CONTRATOS_Y_MAQUINAS_DE_ESTADO.md) y los JSON Schema del directorio `contracts/` del paquete v1.1.

## 3. Núcleo del agente Python F1–F2 — implementado

El paquete está en `agent/`, con punto de entrada `agent/src/bapps_sync_agent/main.py` y empaquetado definido por `agent/pyproject.toml`.

Componentes ya presentes:

- `application/agent_service.py`: ciclo de heartbeat, actualización de configuración, claim de comandos y vaciado de outbox.
- `application/sync_runner.py`: un worker, reserva por sincronización, parada cooperativa y eventos `run_started`/`run_finished`.
- `application/command_handler.py`: `run_now`, `stop_run`, pausa, reanudación y refresco de configuración con journal idempotente.
- `infrastructure/outbox.py`: persistencia JSON atómica, recuperación de eventos en envío y reintentos.
- `infrastructure/config_store.py`, `command_journal.py` y `single_instance_lock.py`: estado local, registro de comandos y exclusión de instancia.
- `infrastructure/api_client.py`: cliente HTTP de los seis endpoints de agente.
- `agent/tests/test_state.py` y `agent/tests/test_sync_runner.py`: pruebas unitarias actualmente incluidas.

La base F1–F2 fue verificada con los **7 tests** del agente usando el runtime bundled del espacio de trabajo.

Pendiente para completar el agente MVP: enrolamiento/operación instalable de extremo a extremo, scheduler basado en los intervalos de configuración, adaptador real `clientes_valery`, gestión de secretos y empaquetado/servicio Windows. El registro de sincronizadores inicial en `main.py` está vacío, por lo que no hay una sincronización real registrada todavía.

La especificación aplicable está en [02_AGENTE_PYTHON.md](backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/02_AGENTE_PYTHON.md).

## 4. API de control Laravel — lectura implementada

El contrato está congelado en [12_CONTRATO_API_CONTROL_v1.md](backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/12_CONTRATO_API_CONTROL_v1.md). Define autenticación de operador, panel, agentes, ejecuciones, auditoría, clientes, catálogo, asignaciones y emisión de comandos.

Están implementadas las consultas, los comandos de agente, la administración de asignaciones y catálogo, el reintento de ejecuciones y la auditoría de control. La central Laravel opera en MySQL `bapps_sync`; SQLite se conserva solo como respaldo histórico y para las pruebas en memoria. La autenticación usa **Laravel Sanctum**: el inicio de sesión emite un bearer con alcance `control-api`, vencimiento de 8 horas y solo almacena su hash en `personal_access_tokens`; `app/Http/Middleware/AuthenticateControlApi.php` lo valida mediante el guard `sanctum`. Un operador puede revocarlo borrando su registro de token, sin cambiar la contraseña ni afectar a los agentes.

La API real respalda los flujos de control ya implementados; MSW solo debe conservarse para cualquier flujo de la SPA que todavía no tenga endpoint real. El siguiente endurecimiento es definir administración de sesiones y permisos por rol en la interfaz, sobre los tokens revocables ya disponibles.

## Secuencia siguiente

1. Implementar las mutaciones restantes de la API de control conforme al contrato v1, endurecer autenticación mediante Sanctum o mecanismo equivalente revocable, y añadir pruebas de contrato frente a los casos MSW.
2. Incorporar scheduler, adaptador `clientes_valery`, enrolamiento operativo y servicio Windows al agente.
3. Verificar la vertical completa: comando desde React → claim por agente → ejecución → outbox → evento → proyección y vista; retirar MSW solo de los flujos ya respaldados por la API real.
4. Ejecutar las pruebas de resiliencia, recuperación e idempotencia definidas en [06_QA_Y_ESTRATEGIA_DE_PRUEBAS.md](backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/06_QA_Y_ESTRATEGIA_DE_PRUEBAS.md) antes de piloto.

## Actualización 2026-07-22: portable y Valery

- Se validó una conexión real y de solo lectura desde el portable hacia Valery/Firebird 2.5 en `C:\ValerySMB\Datos\VALERY3.MDF`, usando `localhost:3050`, `SYSDBA` y charset `iso8859_1`.
- El portable usa `firebirdsql` y `passlib` para soportar `Legacy_Auth`; no requiere `fbclient.dll`.
- La autoprueba interna de `BAPPS-Sync-Agent.exe` finalizó con código `0` y la suite actual del agente tiene 12 pruebas correctas.
- El enrolamiento operativo desde la GUI, heartbeat y refresco de configuración ya están validados en LAN. Sigue sin existir un sincronizador real registrado; el plan vigente está en [PLAN_CONTINUACION_2026-07-22.md](PLAN_CONTINUACION_2026-07-22.md).

## Actualización 2026-07-22: P1 validado y P2 implementado

- P1 se validó manualmente desde una PC Valery: el agente `AGT-VALERY-01` se enroló contra `http://192.168.0.116:8000`, quedó conectado y emitió heartbeat.
- P2 agrega un destino MySQL BAPPS por agente, cifrado en Laravel y entregado solo a portables `0.2.0` mediante el contrato `1.1`.
- El portable P2 lo cifra nuevamente con Windows DPAPI, muestra metadatos no sensibles y permite probar el destino MySQL. No muestra contraseña.
- La configuración temporal del centro se realiza con `php artisan bapps:configure-mysql-target`. La migración, las pruebas Laravel y la conexión MySQL real ya fueron validadas desde la PC Valery el 2026-07-22; el siguiente pendiente es el sincronizador `clientes_valery`.

## Actualización 2026-07-22: P3 listo para ejecución controlada

- El portable 0.3.0 incorpora el sincronizador `clientes_valery` y lo registra en el runtime.
- Firebird se consulta solo mediante `SELECT`; MySQL BAPPS recibe upserts por `codigo` en `clientes_valery_sync`.
- La primera ejecución se solicita con `bapps:queue-run`; queda deliberadamente manual hasta confirmar datos, idempotencia y eventos de ejecución.
- La implementación y el portable fueron verificados localmente y la primera ejecución real desde la PC Valery fue correcta el 2026-07-22. Antes de scheduler queda repetir una ejecución y comprobar explícitamente la idempotencia por `codigo`.

## Actualizacion 2026-07-22: servicio Windows preparado

- El agente ya tiene un host `BAPPSyncAgent` para el Service Control Manager, independiente de la GUI.
- El build separa GUI y servicio; la instalacion/desinstalacion administrativa se hace mediante scripts PowerShell y conserva el estado en `C:\ProgramData\Bapps\SyncAgent`.
- Los secretos nuevos se protegen con DPAPI de maquina. La GUI migra en su primera apertura los secretos de usuario existentes para que el servicio pueda leerlos sin exponerlos.
- Verificado: 23 pruebas Python, importacion `pywin32`, autoprueba congelada del servicio y sintaxis de scripts.
- Se genero el paquete final `agent/release/BAPPS-Sync-Agent-0.4.1-windows-x64.zip` usando un Python aislado con Tcl/Tk; contiene la GUI, el servicio, scripts y guia de instalacion. El hotfix corrige el comando de registro del servicio y propaga errores al instalador.
- Aun falta la prueba en PC Valery como administrador, con GUI cerrada y heartbeat/scheduler observables.

## Actualización 2026-07-23: instalador gráfico de servicio

- La distribución final de prueba deja de requerir comandos PowerShell para el
  usuario: el artefacto es
  `agent/release/BAPPS-Sync-Setup-0.4.7.exe`.
- El instalador NSIS solicita UAC, detiene una instancia de servicio existente
  antes de actualizar sus binarios, instala GUI/servicio, prepara los secretos
  DPAPI y registra/inicia `BAPPSyncAgent` internamente.
- Se corrigió el timeout 1053 de 0.4.1: cuando el ejecutable congelado se
  inicia sin argumentos por Windows, entra ahora al dispatcher del Service
  Control Manager en vez de procesar la línea de comandos como una ejecución
  interactiva.
- La reconstrucción PyInstaller, la autoprueba del servicio, las 23 pruebas
  Python y la compilación del Setup fueron correctas.
- Pendiente de cierre: instalar 0.4.7 en Valery, cerrar la GUI y comprobar
  heartbeat y una ejecución desde el Centro BAPPS. La firma de código sigue
  pendiente antes de una distribución productiva amplia.
