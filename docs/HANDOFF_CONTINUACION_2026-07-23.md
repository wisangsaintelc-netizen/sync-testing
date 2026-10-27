# BAPPS Sync — relevo de trabajo (2026-07-23)

> Referencia vigente: `docs/HANDOFF_CONTINUACION_2026-07-27.md`. Este archivo
> se conserva como historial; el nuevo handoff es la guía autoritativa para
> continuar.

Este documento permite continuar el proyecto en otro chat sin reconstruir el
contexto. La fuente de estado operativo también es `docs/ONGOING.txt`; este
archivo prioriza las acciones pendientes y verificadas.

## Estado actual

La vertical productiva `clientes_valery` está operativa de punta a punta:

```text
Firebird Valery (CLIENTES)
  -> BAPPS Sync Agent Windows
  -> Centro Laravel
  -> MySQL BAPPS (clientes_valery_sync)
  -> bitácoras locales sync_success / sync_errors
```

- Agente real: `AGT-VALERY-01`, conectado por LAN al Centro
  `http://192.168.0.116:8000`.
- Fuente real: Firebird en `localhost:3050`, archivo
  `C:\ValerySMB\Datos\VALERY3.MDF`; la conexión fue comprobada correctamente.
- Destino BAPPS: configuración MySQL recibida por el agente desde el Centro;
  credenciales protegidas y no visibles en la GUI.
- La sincronización real lee `CLIENTES` y escribe en
  `clientes_valery_sync`. Se verificaron 369 registros y ejecución idempotente.
- El servicio Windows permanece enviando heartbeat cada 30 segundos aunque la
  GUI esté cerrada.

## Entregable más reciente

Archivo listo para probar, sin haber tocado la instalación estable de Valery:

```text
agent/release/BAPPS-Sync-Setup-0.5.2.exe
Tamaño: 16,530,295 bytes
SHA-256: 09211F96E82CBA29319E8D7CE773361C8451014B592A4EF6A007FE44CBB4225F
```

Versión 0.5.2 incorpora el protocolo de reintento seguro. La versión que se
ve actualmente en Valery es anterior, por lo que el endpoint de reintento se
rechaza conscientemente hasta actualizar el agente. Esto evita ejecuciones
duplicadas.

## Trabajo local posterior al relevo: auditoría de mutaciones

Se añadió `RecordControlAudit` para que la auditoría visible del Centro deje
de depender solo de datos demo o inserciones manuales. Ahora se persisten,
dentro de la misma transacción de la mutación, eventos para:

- comandos emitidos (`run_now`, `stop_run`, `pause_sync`, `resume_sync` y
  `refresh_config`);
- cambio directo de una asignación agente/sync y los cambios de asignación
  provocados por pausar o reanudar;
- creación y edición de catálogo;
- reintentos de ejecuciones fallidas.

Cada evento conserva actor, objetivo, acción y contexto operativo mínimo. No
se registran contraseñas, configuraciones cifradas ni otros secretos.

Archivos principales:

- `app/Actions/ControlApi/RecordControlAudit.php`
- `app/Actions/ControlApi/QueueAgentCommand.php`
- `app/Actions/ControlApi/UpdateAgentSync.php`
- `app/Actions/ControlApi/RetryFailedRun.php`
- `app/Http/Controllers/ControlApi/SyncCatalogController.php`

Se ampliaron `ControlApiAgentMutationTest`,
`ControlApiCatalogMutationTest` y `RetryFailedRunTest` con aserciones de
auditoría. Validación realizada el 2026-07-23: las tres suites pasaron (8
pruebas y 50 aserciones) y Pint pasó sobre los cuatro archivos modificados.
El `pint --test` global aún reporta tres incidencias de estilo preexistentes en
`ClientListResource.php`, `routes/api.php` y `routes/console.php`; no forman
parte de este cambio.

## Capacidades implementadas y verificadas

| Bloque | Estado | Evidencia |
|---|---|---|
| P1 — Enrolamiento, identidad y heartbeat | Validado | `AgentApiTest`: 7 pruebas / 33 aserciones |
| P2 — MySQL BAPPS administrado por Centro | Validado | `ConfigureAgentBappsMysqlTest`: 1 / 6 |
| P3 — Firebird `CLIENTES` a MySQL BAPPS | Validado real | 369 registros, upsert idempotente |
| P4/F7 — Servicio, scheduler, comandos y pausa | Validado | 34 Python; pausa muestra `Pausado` en panel |
| F5 — `sync_success` / `sync_errors` locales | Validado real | Log MySQL real con run, métricas y duración |
| F8 — Lecturas de clientes, auditoría y catálogo | Validado | `ControlApiReadCoverageTest`: 2 / 13 |
| F8 — Mutaciones de catálogo | Validado | `ControlApiCatalogMutationTest`: 3 / 17 |
| F8 — Reintento seguro | Validado end-to-end | Reintento real 0.5.2: una sola ejecución nueva, `success`, 369 actualizadas |
| F8 — Auditoría de mutaciones | Validado | 8 pruebas / 50 aserciones; Pint focalizado correcto |
| Frontend | Compilado | `npm.cmd run build` correcto |

El agente mantiene UTC para eventos centrales. A partir de 0.5.1 las tablas
locales MySQL `sync_success` y `sync_errors` usan la hora local de la PC para
evitar que un `DATETIME` parezca adelantado cuatro horas en Caracas.

## Reintento 0.5.2: comportamiento exacto

Ruta: `POST /api/v1/runs/{run_id}/retry`.

1. El Centro exige que la ejecución original esté en estado `failed`.
2. Comprueba que el agente, el catálogo y la asignación estén habilitados.
3. Exige agente `>= 0.5.2`.
4. Crea transaccionalmente una nueva `sync_runs` con estado `pending` y otro
   `run_id`.
5. Publica `run_now` incluyendo ese mismo `run_id` en el payload.
6. El agente 0.5.2 conserva dicho identificador al iniciar la ejecución.
7. Los eventos `run_started` y `run_finished` actualizan esa misma ejecución.

No eliminar esta comprobación de versión: un agente anterior ignora el
`run_id` preasignado y generaría otro, lo que rompería la trazabilidad.

Archivos clave:

- `app/Actions/ControlApi/RetryFailedRun.php`
- `app/Http/Controllers/ControlApi/RunController.php`
- `agent/src/bapps_sync_agent/application/command_handler.py`
- `agent/src/bapps_sync_agent/application/sync_runner.py`
- `agent/src/bapps_sync_agent/domain/runs.py`
- `tests/Feature/RetryFailedRunTest.php`
- `agent/tests/test_command_handler.py`
- `agent/tests/test_sync_runner.py`

## Cómo arrancar el Centro en desarrollo LAN

No usar `composer run dev` en Windows: incluye Laravel Pail, que requiere
`pcntl` y termina los demás procesos. Usar terminales separadas desde la raíz
del proyecto:

```powershell
# Terminal 1: backend accesible desde otras PCs de la LAN
php artisan serve --host=0.0.0.0 --port=8000

# Terminal 2: frontend Vite accesible desde la LAN
npm.cmd run dev -- --host 0.0.0.0

# Terminal 3: necesaria si se usan jobs de Laravel
php artisan queue:listen --tries=1 --timeout=0
```

Abrir desde otra PC: `http://192.168.0.116:8000` mientras esa sea la IP LAN
del Centro. Si cambia, actualizar el bootstrap del agente o reenrolar según
corresponda. El CORS de Vite se resolvió usando `--host 0.0.0.0`.

Usar una cuenta de operador ya creada en el Centro; no guardar contraseñas en
documentación ni en comandos de consola.

## Prueba integrada de reintento: validada el 2026-07-23

La actualización del agente a 0.5.2 quedó confirmada por heartbeat de
`AGT-VALERY-01` Online. Se creó una falla sintética controlada y reintentable
con `bapps:create-retry-test-run`; no se alteraron Firebird, MySQL BAPPS ni la
configuración del agente.

Evidencia observada en el panel:

- ejecución de origen: `RUN-RETRY-TEST-8c171b52-a4f7-4ac0-be4a-09517c538490`;
- nueva ejecución por el reintento: `RUN-22173012-4f4e-483a-ac2c-230bf4ebd1c8`;
- trigger de la nueva ejecución: `command`;
- resultado: `success`, 4.0 s, 369 leídas, 0 insertadas, 369 actualizadas y
  0 fallidas.

No se observó una segunda ejecución para el mismo reintento. Esto confirma el
protocolo de `run_id` preasignado de extremo a extremo: Centro → comando →
agente 0.5.2 → eventos → panel.

Si el instalador informa un error, conservar el mensaje y revisar el Visor de
eventos de Windows, origen `BAPPSyncAgent`. No ejecutar scripts PowerShell de
instalación: son solo diagnóstico histórico; el flujo de usuario es el Setup
con doble clic.

### Preparación controlada realizada el 2026-07-23

El agente `AGT-VALERY-01` ya reporta versión `0.5.2`, estado `Online` y
heartbeat correcto. Como no había una ejecución fallida real que reintentar, se
añadió el comando de Centro `bapps:create-retry-test-run`; crea exclusivamente
una fila central `sync_runs` con el código reintentable
`TARGET_CONNECTION_FAILED` y un mensaje técnico que identifica la prueba, y no ejecuta ni
reconfigura el agente. La prueba del comando pasó (1 prueba / 2 aserciones) y
Pint pasó sobre los archivos modificados.

La primera ejecución de preparación usó un código no catalogado y la UI no la
marcó reintentable. El comando se corrigió para usar el código reintentable
`TARGET_CONNECTION_FAILED`, preservando un mensaje técnico que identifica la
prueba como sintética. La validación integrada anterior se hizo con esa
corrección.

## Comandos de validación

Desde `C:\Sync\Valery\bapps-sync`:

```powershell
php artisan test --filter=RetryFailedRunTest
php artisan test --filter=AgentApiTest
php artisan test --filter=ControlApiCatalogMutationTest
php artisan test --filter=ControlApiReadCoverageTest
npm.cmd run build
```

Desde `C:\Sync\Valery\bapps-sync\agent`, si existe el entorno virtual:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado validado actual: 34 pruebas Python correctas.

## Recompilar un instalador futuro

El entorno aislado de compilación creado está en `agent\.venv`. Las
dependencias se instalan con `.[portable]`. Se añadió un compilador portable
en `agent\tools\nsis-3.12\Bin\makensis.exe`; no se instaló NSIS en Windows.

```powershell
cd C:\Sync\Valery\bapps-sync\agent

# Solo si cambió el código Python
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_portable.ps1 `
  -Python .\.venv\Scripts\python.exe -SkipDependencies

# Empaquetar con la versión que corresponda
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1 `
  -Version 0.5.3 -NsisCompiler .\tools\nsis-3.12\Bin\makensis.exe

.\dist\BAPPS-Sync-Service\BAPPS-Sync-Service.exe --portable-self-test
Get-FileHash .\release\BAPPS-Sync-Setup-0.5.3.exe -Algorithm SHA256
```

No crear ni modificar servicios Windows durante la compilación. La única
máquina que debe cambiar al ejecutar el Setup es la PC de prueba elegida.

## Próxima prioridad después de la prueba integrada

1. Continuar el plan maestro desde F9 (hardening QA), empezando por los P0
   pendientes que puedan validarse sin alterar la instalación de Valery. El
   primer caso agregado fue outbox corrupta: se aisló sin bloquear eventos
   válidos posteriores; validado junto a la suite Python de 35 pruebas. El
   segundo caso fue reinicio con ejecución inconclusa: emite `interrupted` con
   `AGENT_RESTARTED` y limpia el estado local; validado en la suite de 36. Se
   validaron además las dos carreras P0 del runner: scheduler + `run_now` no
   puede duplicar el sync activo, y `stop_run` concurrente con la finalización
   genera un único evento terminal. En el Centro, `AgentApiTest` validó que un
   `run_started` tardío no revierte una ejecución terminal (8 pruebas / 39
   aserciones). Se corrigió además la configuración local corrupta: cada
   guardado conserva `active-config.last-valid.json` y el agente usa esa copia
   si `active-config.json` es ilegible. Suite Python actual: 39 pruebas
   correctas. Se validó asimismo que una caída del Centro conserva la
   telemetría en outbox y no detiene el scheduler local, y que una caída del
   MySQL BAPPS se detecta antes de abrir Firebird. Suite Python actual: 41
   pruebas correctas. Estos cambios están solo en fuente: no se ha reconstruido
   ni instalado un artefacto nuevo en Valery. En el Centro se validó además la
   idempotencia del resultado de comandos y su exposición correcta al panel,
   junto con la prohibición de completar un comando ajeno (`AgentApiTest`: 10
   pruebas / 50 aserciones). Antes de empaquetar, falta una regresión completa
   de Laravel, frontend y agente.

## Entrega 0.5.3 preparada: hardening F9

La regresión completa pasó el 2026-07-23:

- Laravel: 31 pruebas / 175 aserciones.
- Pint: correcto; normalizó dos imports preexistentes.
- Frontend: `npm.cmd run build` correcto.
- Agente: 42 pruebas Python correctas.
- Servicio empaquetado: `--portable-self-test` correcto.

Artefacto listo pero **no instalado** en Valery:

```text
agent/release/BAPPS-Sync-Setup-0.5.3.exe
Tamaño: 16,531,485 bytes
SHA-256: 13B742FE84893D528AEB338520946F9CAA5DDFE68E3F3C854D3F344A8EB9F430
```

Incluye la copia de última configuración válida, protección de outbox no
escribible, continuidad durante caída del Centro y la comprobación temprana
del destino MySQL antes de abrir Firebird. No instalar sin decisión explícita:
la 0.5.2 que opera en Valery permanece estable.

## Corrección 0.5.4: versión reportada por heartbeat

Después de instalar 0.5.3, `AGT-VALERY-01` seguía mostrando `0.5.2` en el
panel aunque el binario nuevo ejecutaba correctamente las sincronizaciones.
La causa fue un valor `0.5.2` fijo en los clientes Python de heartbeat y
enrolamiento. Laravel guarda literalmente `agent_version` del heartbeat en
`agents.version`, y el panel muestra ese campo; no deduce la versión desde el
nombre del instalador.

La versión se centralizó en `bapps_sync_agent.__version__`; heartbeat y
enrolamiento consumen esa misma constante. Las pruebas verifican ambos
payloads. Suite Python: 43 pruebas correctas. Artefacto correctivo validado e
instalado posteriormente en Valery:

```text
agent/release/BAPPS-Sync-Setup-0.5.4.exe
Tamaño: 16,529,827 bytes
SHA-256: B35A58C71732F38691193EA026BAC75D6FDED4514B9E58E1D0DB54E4DB0AEF4B
```

La verificación visual posterior confirmó `AGT-VALERY-01` en versión `0.5.4`,
Online y con heartbeat reciente. No requiere nueva intervención en Valery.

## Endurecimiento de autenticación de control: Sanctum revocable

El bearer de operador ya no es un HMAC estateless. Se integró
`laravel/sanctum` 4.3, la migración central
`2026_07_23_200000_create_personal_access_tokens_table.php` y el trait
`HasApiTokens` en `User`. Al iniciar sesión se invalida el token previo llamado
`control-api` y se emite uno nuevo con alcance `control-api` y vencimiento de
8 horas. La base central almacena solamente su hash; eliminar el registro del
token revoca el acceso de inmediato. El middleware existente conserva la
respuesta pública `UNAUTHENTICATED` y valida mediante el guard `sanctum`.

La prueba focal `ControlApiReadTest` pasó con 5 pruebas y 41 aserciones; Pint
pasó sobre usuario, login, middleware, configuración, migración y prueba. Este
cambio afecta únicamente el acceso de operadores al Centro: no modifica el
protocolo, credenciales ni instalación del agente Valery.

## Continuación 2026-07-27: regresión y carrera `run_now`

La migración de Sanctum se aplicó inicialmente a la SQLite histórica. La regresión
completa posterior pasó: Laravel 32 pruebas / 179 aserciones, Pint correcto y
`npm.cmd run build` correcto. La SPA conserva su comportamiento de redirigir a
`/login` ante un 401, por lo que los bearer anteriores quedan reemplazados por
un login nuevo sin afectar al agente.

Se añadió la cobertura explícita de dos comandos manuales `run_now` para el
mismo `sync_code`: mientras el primero está en ejecución, el segundo recibe
`SYNC_ALREADY_RUNNING`; el sincronizador se invoca una sola vez. La suite
Python completa pasó con 44 pruebas. No se generó ni instaló ningún artefacto
nuevo en Valery.

También se reforzó la frontera HTTP del agente contra payloads excesivos. El
middleware `agent.payload` limita cada solicitud de la API de agente a 64 KiB
(`BAPPS_SYNC_AGENT_MAX_REQUEST_BYTES`, configurable) y responde `413
PAYLOAD_TOO_LARGE` antes de autenticación o persistencia. Se limitaron además
los identificadores y la lista de ejecuciones del heartbeat. `AgentApiTest` pasó
con 12 pruebas / 56 aserciones, incluida la garantía de que un evento de 70 KiB
no llega a `sync_events`; Pint pasó. No afecta al instalador ni a Valery.

La API también cubre explícitamente la expiración: antes de cada claim, un
comando vencido pasa a estado `expired` y no se entrega al agente. La prueba
`AgentApiTest` pasó con 11 pruebas / 53 aserciones antes del control de tamaño;
después de ambos controles, el mismo grupo pasó con 12 / 56.

Se corrigió además una exposición potencial de secretos: una excepción
inesperada de un driver ya no propaga su texto crudo a outbox, Centro ni
`sync_errors` local. Se conserva `UNEXPECTED_SYNC_ERROR` con un diagnóstico
seguro. La prueba inyecta una URI con contraseña y token y verifica que ninguno
aparece en los eventos persistidos. Suite Python completa: 45 pruebas
correctas. Este cambio sigue solo en código fuente; no se ha empaquetado ni
instalado un agente nuevo.

Regresión de cierre 2026-07-27: Laravel completo pasó con 34 pruebas / 185
aserciones y Pint completo pasó. La suite Python vigente pasó con 45 pruebas.
El build de React ya había pasado en esta misma sesión y no hubo cambios de
frontend posteriores. El siguiente gate F9 que aporta evidencia nueva es un
soak/reconexión controlado con el Centro fuera de línea durante un período
prolongado; no debe realizarse sobre Valery sin acordar antes la ventana de
prueba.

## Estandarización de sincronizadores y transición de central a MySQL

La lógica de sincronización no vive en Laravel ni en SQLite. Está en el agente,
en `agent/src/bapps_sync_agent/syncs/`: `clientes_valery.py` implementa la
lectura Firebird y el upsert al MySQL BAPPS del cliente. El registro fue
normalizado en `syncs/builtins.py`; `application/runtime.py` solo consume
`create_builtin_synchronizer_registry()`. Cada sincronizador futuro declara su
`CODE`, implementa el protocolo `run(SyncContext) -> SyncResult` y se registra
en ese único archivo.

La central Laravel ya opera en MySQL `bapps_sync` local. Se actualizó el valor
predeterminado de `config/database.php` y `.env.example` a MySQL, mientras que
`phpunit.xml` conserva SQLite en memoria exclusivamente para pruebas. La guía
completa está en `docs/ARQUITECTURA_SINCRONIZADORES_Y_DATOS.md`.

Validación: suite Python 46 pruebas correctas; Laravel 34 pruebas / 185
aserciones y Pint correctos. No se empaquetó ni instaló un agente nuevo.

### Ejecución de la transición SQLite -> MySQL

La conexión MySQL `127.0.0.1:3306` se validó y se creó la base central
`bapps_sync` con `utf8mb4`. El primer intento de migración reveló una limitación
del servidor sobre múltiples `TIMESTAMP` sin valor por defecto; se corrigieron
los campos operativos de la migración central a `DATETIME`, sin cambiar su
semántica Laravel. Las siete migraciones quedaron aplicadas en MySQL.

Se añadió `bapps:copy-central-sqlite-to-mysql`, que exige un destino vacío y
copia en orden de dependencias. La transferencia real preservó: 2 usuarios, 1
cliente, 1 catálogo, 2 agentes, 2 asignaciones, 20 comandos, 190 ejecuciones, 376
eventos, 4 auditorías y 1 token Sanctum. Eloquent confirmó en MySQL 2 agentes,
190 ejecuciones y 376 eventos. La SQLite queda como respaldo histórico; Firebird y
el MySQL BAPPS del cliente no fueron modificados. Regresión posterior: Laravel
34 pruebas / 185 aserciones y Pint correctos.

### Estado visible de agentes por heartbeat

Se corrigió una inconsistencia observada en el panel: `AGT-DEMO` mostraba
`Online` con un heartbeat de nueve días. El campo `agents.status` conserva el
último estado reportado, pero ya no define por sí solo el estado operativo. Un
agente es visible como `online` únicamente si su último heartbeat tiene menos
de 120 segundos (`BAPPS_SYNC_AGENT_ONLINE_THRESHOLD_SECONDS`), equivalente a
cuatro intervalos de 30 s; después se resuelve como `offline`. Deshabilitados y
agentes aún no enrolados preservan sus estados propios.

La regla vive en `Agent::visibleStatus()` y sus scopes, y se aplica igual a
lista, drawer, filtros, métricas del dashboard y salud de clientes. MySQL
confirmó que `AGT-DEMO` se resuelve como `offline`; `AGT-VALERY-01` continuará
online mientras siga reportando. Validación: Laravel completo 35 pruebas / 198
aserciones y Pint correctos.

### Navegación acotada del detalle de agentes

El listado de agentes ya se consulta paginado en el servidor (25 por página).
El resumen `1–N de total` ahora permanece visible aun cuando sólo haya una
página, para que no se confunda con un scroll infinito. En el drawer, Comandos
recientes, Ejecuciones recientes y Timeline se muestran en páginas locales de diez
elementos con Anterior/Siguiente. La API mantiene sus límites de contrato: 20
comandos, 20 ejecuciones y 50 eventos de timeline recientes; para el historial
completo se usa el listado paginado de Ejecuciones/Auditoría.

El botón antes llamado `Refrescar config` se renombró a `Actualizar
configuración`. Encola el comando `refresh_config`: cuando el agente lo recibe
en su siguiente sondeo, vuelve a descargar las asignaciones y parámetros
vigentes. No ejecuta un sincronizador ni toca Firebird o el MySQL BAPPS del
cliente. Build de React de producción correcto (`npm.cmd run build`).

El detalle de un cliente incluye ahora `errors`: las diez ejecuciones fallidas más
recientes, separadas del historial general. Así una salud `error` y su contador
de errores abiertos tienen diagnóstico visible y cada entrada abre la ejecución.
Los IDs operativos se muestran compactos (`RUN-451a…`, `CMD-13EA…`) con el
valor completo disponible al posar el cursor, y las ejecuciones/comandos muestran
su hora local. El paginador compacto se comparte entre el drawer de agentes y
el de clientes.

### Alertas revisables vs. salud operativa

Una ejecución `failed` es historial inmutable, pero ahora puede reconocerse con
`Marcar revisado`. La acción persiste `reviewed_at` y `reviewed_by` en
`sync_runs` y registra `error/review_run` en Auditoría. Una alerta revisada sale
de los contadores y del filtro `Alertas`, pero la ejecución conserva su estado
Failed y su diagnóstico en el historial. No hay borrado ni cambio artificial
de resultado.

La salud del cliente ya no se degrada a `error` por fallos históricos: se basa
en la disponibilidad visible de sus agentes (`ok`, `warning` o `enrolled`). El
conteo de alertas es independiente. El dashboard y el contador del menú ahora
cuentan solamente fallos sin revisar de las últimas 24 h. La migración
`2026_07_27_210000_add_review_tracking_to_sync_runs_table.php` debe ejecutarse
en la central MySQL con `php artisan migrate` antes de usar esta función.
2. Mantener observación operativa de la vertical `clientes_valery` y conservar
   la evidencia de servicio, scheduler y reintento en el panel.
3. Continuar el plan maestro sin
   alterar P1–P4 ni la vertical `clientes_valery` validada.

## Instrucción sugerida para el otro chat

```text
Trabaja en C:\Sync\Valery\bapps-sync. Lee primero docs/HANDOFF_CONTINUACION_2026-07-23.md,
docs/ONGOING.txt y docs/BAPPS_SYNC_PLAN_MAESTRO_v1.1.md. No reinstales ni
modifiques el agente estable de Valery sin pedirlo explícitamente. Continúa
desde la prueba integrada del reintento 0.5.2; conserva las validaciones y
documenta con precisión cada cambio y prueba realizada.
```
