# Plan de continuación BAPPS Sync

**Fecha:** 2026-07-22  
**Estado:** aprobado para retomar la implementación.

## Punto de partida confirmado

- El portable `agent/dist/BAPPS-Sync-Agent/` abre una GUI local.
- La PC de Valery logró conexión real y de solo lectura contra Firebird 2.5:
  - Host: `localhost`
  - Puerto: `3050`
  - Base: `C:\ValerySMB\Datos\VALERY3.MDF`
  - Usuario: `SYSDBA`
  - Charset: `iso8859_1`
- El agente usa `firebirdsql`, sin dependencia de `fbclient.dll`.
- `passlib` está incluido para `Legacy_Auth` de Firebird 2.5.
- La autoprueba del ejecutable congelado finalizó correctamente.
- Hay 12 pruebas automatizadas del agente correctas.
- Laravel ya dispone de endpoints de enrolamiento, autenticación de agente, heartbeat, configuración, comandos y eventos.

## Objetivo de la siguiente vertical

Completar este recorrido verificable:

```text
Portable personalizado
  -> bootstrap local
  -> enrolamiento Laravel
  -> identidad segura local
  -> heartbeat y configuración
  -> agente visible online en el centro
```

No se ejecutará todavía una sincronización de negocio hasta que esta vertical esté comprobada en la PC de Valery.

## P0 — Actualización documental

Actualizar los documentos de estado sin modificar el Development Pack v1.1, que continúa siendo la especificación de referencia.

- `docs/ESTADO_IMPLEMENTACION.md`: reflejar la conexión real Firebird, los 12 tests y el portable validado.
- `docs/ESTADO_AGENTE_PORTABLE_2026-07-17.md`: cerrar el pendiente de conexión Firebird y conservar el historial de correcciones `firebirdsql`/`passlib`.
- `docs/ONGOING.txt`: resumir el hito y enlazar este plan.
- `docs/GUIA_PRUEBA_VERTICAL.md`: agregar el procedimiento de prueba con el portable real.

## P1 — Bootstrap, enrolamiento y heartbeat

### Bootstrap

Cada carpeta portable se entregará con un `bootstrap.json` personalizado, ubicado junto al ejecutable:

```json
{
  "schema_version": "1.0",
  "base_url": "http://servidor-bapps:8000",
  "agent_code": "AGT-DEMO",
  "enrollment_token": "credencial-de-un-solo-uso",
  "issued_at": "2026-07-22T00:00:00Z"
}
```

Reglas:

- La GUI no permitirá editar URL, código ni token.
- La URL deberá ser alcanzable desde la PC de Valery. `localhost` solo sirve si Laravel corre en esa misma PC.
- El bootstrap no se guarda en el repositorio ni se comparte como plantilla con secretos reales.
- El comando Laravel de aprovisionamiento de desarrollo generará el bootstrap. La provisión desde la UI de control se realizará posteriormente.

### Enrolamiento

- Al abrir el agente, si no existe identidad local y hay bootstrap válido, hará `POST /api/v1/agent/enroll` automáticamente.
- El agente guardará la identidad resultante (`agent_code`, `agent_token`, `base_url`) en el directorio de estado.
- El token definitivo se protegerá con Windows DPAPI; identidades antiguas en texto plano se migrarán al volver a cargarse.
- El token de enrolamiento deja de ser válido en Laravel al rotarse la credencial.
- Si falla, la GUI mostrará un diagnóstico operativo y el botón **Reintentar enrolamiento**. No permitirá alterar la identidad.

### Runtime y estado visible

- Después de enrolarse, el control loop se iniciará en segundo plano mientras la GUI esté abierta.
- Heartbeat: cada 30 segundos con jitter.
- Polling de comandos: cada 5 segundos con jitter.
- Configuración: se descarga al iniciar y cuando el centro informe una nueva versión.
- Un archivo de estado atómico registrará último intento, último heartbeat correcto, error actual, versión de configuración y estado online/offline.
- La GUI leerá ese estado para mostrar URL, agente, conexión y último heartbeat.
- Al cerrar la GUI, el runtime se detendrá ordenadamente. El servicio Windows reutilizará este mismo núcleo en una entrega posterior.

### Criterio de aceptación P1

1. Copiar la carpeta portable a la PC de Valery con un bootstrap válido.
2. Abrir el agente y verificar enrolamiento automático.
3. Confirmar que el agente aparece online mediante la API Laravel y que `last_seen_at` cambia.
4. Cerrar y abrir el agente; debe conservar la identidad y reanudar heartbeats.
5. Confirmar que no hay token en texto plano en el estado local.

## P2 — Configuración MySQL BAPPS administrada por el centro

El agente seguirá configurando localmente solo la fuente Valery/Profit. El destino MySQL BAPPS será administrado desde BAPPS Sync y visible como solo lectura en el agente.

- Introducir configuración agente-centro `schema_version: 1.1` compatible con la actual 1.0.
- Añadir `targets.bapps_mysql`: host, puerto, base, usuario y contraseña.
- Cifrar la contraseña en Laravel en reposo y protegerla con DPAPI al llegar al agente.
- Mostrar host, base, usuario, fecha de recepción y prueba de conexión; nunca mostrar la contraseña.
- Mantener agentes que solo entienden 1.0 sin interrupción durante la transición.

Estado 2026-07-22: implementación lista; falta migrar Laravel y validar la conexión contra el MySQL BAPPS real. La operación temporal se hace con `bapps:configure-mysql-target`; la pantalla React de edición queda para P4, cuando se sustituyan los datos MSW por la API de control real.

## P3 — Sincronizador real `clientes_valery`

Tomar como referencia el comportamiento ya validado de `C:\Sync\Valery\sync_clientes_valery\sync_clientes.py`.

- Fuente: Firebird mediante `firebirdsql`, tabla `CLIENTES`, charset `iso8859_1`.
- Destino: MySQL BAPPS, tabla `clientes_valery_sync`.
- Idempotencia por `codigo` y upsert.
- Lotes iniciales de 200 registros.
- Firebird siempre se usa en modo solo lectura.
- El agente reporta conteos, duración y errores; no envía los datos administrativos al centro.
- Registrar el sincronizador en `SynchronizerRegistry` y permitir inicialmente solo ejecución manual.
- Persistir `run_started` y `run_finished` en outbox; escribir éxito/error en las tablas locales previstas.

Estado 2026-07-22: implementación lista para prueba real. Se añadió el sincronizador al runtime del portable 0.3.0 y `bapps:queue-run` para disparar la primera ejecución sin volver a aprovisionar ni invalidar la credencial del agente.

Validación 2026-07-22: dos ejecuciones manuales reales correctas desde Firebird Valery hacia MySQL BAPPS. La segunda dejó `369` registros y `369` códigos distintos en `clientes_valery_sync`, confirmando idempotencia por `codigo`. P3 completado; no habilitar intervalos hasta P4.

### Criterio de aceptación P3

1. Ejecutar una ejecución limitada desde un comando `run_now`.
2. Comparar registros de muestra contra Valery/DBeaver.
3. Repetir la ejecución y confirmar upsert idempotente por `codigo`.
4. Simular caída del centro y verificar recuperación por outbox.
5. Simular caída del MySQL destino y verificar que Firebird no se modifica.

## P4 — Panel, scheduler, servicio e instalador

- Completar mutaciones de la API de control para emitir comandos y administrar asignaciones.
- Conectar la vista React de agentes/ejecuciones al backend real para la vertical de comandos.
- Habilitar scheduler local por intervalos solo después de validar ejecución manual.
- Convertir el runtime en servicio Windows; la GUI quedará como panel de estado y configuración.
- Generar instalador versionado después de estabilizar el portable.

Estado 2026-07-22: en curso. Se implementaron las mutaciones reales de comando y asignación para agentes (`POST /agents/{code}/commands`, `PATCH /agents/{code}/syncs/{syncCode}`) y se desactivó MSW en la configuración local para que el panel consulte Laravel. `ControlApiAgentMutationTest` pasó (2 tests/10 aserciones) y el listado real de agentes fue validado visualmente. Pendiente: validar ejecución desde el drawer, scheduler, servicio Windows e instalador.

Validación 2026-07-22: scheduler local probado desde el panel con una ejecución automática `schedule` correcta: 369 leídas, 0 insertadas, 369 actualizadas, 0 fallidas, duración 5.0 s. Pendiente P4: servicio Windows e instalador.

## F5 — Logs locales MySQL BAPPS (actualización 2026-07-23)

Implementado: el agente incorpora `LocalSyncLogRepository`, conectado al
`SyncRunner`. Usa el destino `targets.bapps_mysql` que publica el Centro BAPPS;
no abre conexiones de escritura contra Firebird. Para `clientes_valery` escribe
la referencia `CLIENTES` → `clientes_valery_sync` en las tablas
`sync_success` o `sync_errors`, y crea dichas tablas si todavía no existen.

La bitácora es no bloqueante: una indisponibilidad de MySQL BAPPS queda
protegida por la telemetría/outbox y no transforma una ejecución correcta en
fallida. Las interrupciones intencionales no se registran como fallos técnicos.

Estado: 28 pruebas unitarias del agente correctas y validación real completa:
la ejecución `RUN-ebd1215585e8458d9491beb7fcdb0612` escribió en `sync_success`
369 leídos, 0 insertados y 369 actualizados en 4,436 ms. Pendiente únicamente
una prueba controlada posterior del fallback con MySQL no disponible.

## F7 — Comandos y recuperación de lease (actualización 2026-07-23)

El agente ya procesa `run_now`, `stop_run`, `pause_sync`, `resume_sync` y
`refresh_config` a través de un journal persistente por `command_id`. Se añadió
cobertura de esa matriz y de los resultados `completed`/`skipped`/`failed`.

El Centro ahora devuelve a `pending` un comando reclamado cuya lease venció
si su expiración global sigue vigente. La validación `AgentApiTest` pasó con 7
pruebas y 33 aserciones, y el agente tiene 32 pruebas correctas. Falta la
prueba operativa desde el panel: pausar el sync, esperar un intervalo sin nueva
ejecución y reanudarlo para observar la siguiente ejecución programada.

La pausa/reanudación actualiza también la asignación central en la misma
transacción que crea el comando; por ello el drawer muestra el estado correcto
al invalidar su consulta. `ControlApiAgentMutationTest` fue validado con 3
pruebas y 18 aserciones. La pausa emitida antes de esta corrección debe
repetirse una vez para centralizar su estado actual.

## F8 — Lecturas reales del Centro (actualización 2026-07-23)

Clientes, Auditoría y Catálogo dejaron de depender de MSW para sus consultas:
Laravel expone sus listados/detalles bajo `/api/v1`, con paginación, filtros y
recursos compatibles con React. La validación `ControlApiReadCoverageTest`
pasó con 2 pruebas y 13 aserciones.

El bloque de catálogo queda implementado y validado en entorno:
persistencia de clave funcional, `POST/PATCH /syncs`, filtro por estado global,
código inmutable e invalidación de configuración de agentes afectados. La
migración `2026_07_23_190000_add_functional_key_to_sync_catalog_table` fue
aplicada y `ControlApiCatalogMutationTest` pasó con 3 pruebas y 17 aserciones.
El siguiente
subbloque es `POST /runs/{id}/retry`: debe preasignar un nuevo `run_id` y el
agente debe respetarlo, de modo que la respuesta cumpla el contrato y no se
dupliquen ejecuciones.

Implementación iniciada: el Centro crea el run como `pending` y publica el
comando con su `run_id`; el agente 0.5.2 lo conserva al iniciar la ejecución.
El endpoint se niega para agentes previos a 0.5.2. La suite Python pasó con
34 pruebas y el instalador 0.5.2 fue generado; falta la prueba integrada
controlada.

Validación Laravel completada: `RetryFailedRunTest` pasó con 2 pruebas y 10
aserciones; `AgentApiTest` pasó con 7 pruebas y 33 aserciones. La validación
Python pasó con 34 pruebas, el servicio congelado superó su autoprueba y la
entrega es `agent/release/BAPPS-Sync-Setup-0.5.2.exe`.

## Pruebas requeridas

### Laravel

- Enrolamiento correcto, token inválido y token consumido.
- Aislamiento entre agentes autenticados.
- Heartbeat actualiza máquina, IP, estado y `last_seen_at`.
- Bootstrap de desarrollo generado con URL y token correctos.

### Agente

- Lectura y validación de bootstrap.
- Enrolamiento, reintento y persistencia DPAPI.
- Migración de identidad heredada.
- Heartbeat/configuración sin bloquear la GUI.
- Autoprueba del ejecutable congelado.

## Decisiones fijadas

- El agente nace con URL y código preconfigurados mediante bootstrap; el usuario local no los escribe.
- La PC Valery solo configura su base fuente local.
- MySQL BAPPS se administra desde el centro y se muestra como solo lectura.
- El primer sincronizador productivo será `clientes_valery`.
- La primera ejecución productiva será manual; scheduler e instalador se posponen hasta validar la vertical completa.

## Actualizacion P4 - Servicio Windows preparado

El runtime se separo de la GUI para operar sin una sesion interactiva de Windows:

- `agent/src/bapps_sync_agent/service_main.py` implementa el servicio `BAPPSyncAgent` usando el Service Control Manager.
- `agent/scripts/build_portable.ps1` genera dos carpetas: `dist/BAPPS-Sync-Agent/` (GUI) y `dist/BAPPS-Sync-Service/` (servicio). El parametro `-ServiceOnly` permite reconstruir solo el host del servicio.
- `agent/scripts/install_service.ps1` copia ambos artefactos a `C:\Program Files\BAPPS Sync Agent` y registra/inicia el servicio. Requiere PowerShell elevado.
- El instalador restringe el ACL de `C:\ProgramData\Bapps\SyncAgent` al usuario propietario, `SYSTEM` y administradores, necesario porque DPAPI de maquina es compartido por GUI y servicio.
- `agent/scripts/uninstall_service.ps1` detiene y elimina el servicio, sin borrar el estado ni las credenciales de `C:\ProgramData\Bapps\SyncAgent`.
- `WindowsSecretProtector` usa DPAPI de maquina al proteger secretos nuevos. Al abrir la GUI actualizada, los archivos existentes protegidos por usuario se descifran y se vuelven a escribir con alcance de maquina, manteniendo compatibilidad.

Verificacion de implementacion el 2026-07-22:

- 23 pruebas Python correctas.
- Importacion de `pywin32` correcta y `BAPPS-Sync-Service.exe --portable-self-test` correcto.
- Sintaxis de ambos scripts PowerShell correcta.

Empaquetado completado: se preparo un Python aislado con Tkinter y se generaron GUI y servicio. El paquete distribuible validado es `agent/release/BAPPS-Sync-Agent-0.4.1-windows-x64.zip`; contiene ambos directorios `dist`, los scripts de instalacion y la guia local. El hotfix 0.4.1 corrige el registro del servicio: `pywin32` recibe `--startup auto install` y cualquier fallo detiene el script. Para la entrega P4 a Valery se debe abrir primero la GUI nueva una vez para migrar DPAPI y solo despues ejecutar el instalador como administrador.

Prueba pendiente de cierre P4:

1. Copiar y extraer `agent/release/BAPPS-Sync-Agent-0.4.1-windows-x64.zip` en la PC Valery.
2. Abrir la GUI una vez y confirmar Firebird/MySQL BAPPS y heartbeat.
3. En PowerShell como administrador ejecutar `install_service.ps1`.
4. Cerrar la GUI, verificar `Get-Service BAPPSyncAgent` y esperar un heartbeat y una ejecución programada.
5. Reabrir la GUI; debe seguir mostrando el estado del servicio y permitir pruebas locales.

## Actualización de distribución — 2026-07-23

La prueba 3 anterior queda reemplazada para el usuario final por:

1. Ejecutar `agent/release/BAPPS-Sync-Setup-0.4.7.exe` con doble clic y
   aceptar la elevación UAC.
2. Cerrar la GUI después de finalizar el asistente.
3. Confirmar en el Centro BAPPS que `AGT-VALERY-01` continúa enviando
   heartbeats y puede ejecutar `clientes_valery` sin una sesión de usuario
   abierta.

Los scripts PowerShell siguen disponibles exclusivamente como utilidad de
diagnóstico. El instalador incorpora la preparación de DPAPI, registro,
actualización e inicio del servicio de forma controlada.
