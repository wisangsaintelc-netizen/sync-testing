# BAPPS Sync — Plan de desarrollo definitivo v1.1

**Fecha:** 15 de julio de 2026  
**Estado:** listo para iniciar codificación por fases.

> **Addendum de implementación (17 de julio de 2026):** el contrato de la API de control React↔Laravel está congelado en `backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/12_CONTRATO_API_CONTROL_v1.md`. Sus tipos y mocks son la referencia ejecutable para esa frontera.

## Nota de consolidación

Este documento supersede las decisiones incompatibles de la especificación v1.0 cuando así se indica en el registro ADR. Está pensado para un equipo de trabajo y para ejecución incremental con Codex.



---

# 01 — Arquitectura y decisiones definitivas

**Versión:** 1.1  
**Fecha:** 15 de julio de 2026  
**Estado:** Fuente de verdad de arquitectura para el MVP.

## 1. Objetivo

Construir una plataforma de control de sincronizadores distribuida, fiable, segura y mantenible, conservando KISS. El centro no reemplaza la ejecución local: la gobierna. El agente no reemplaza al centro: ejecuta y reporta.

## 2. Alcance del MVP

El MVP cubre:

- Enrolamiento individual de agentes.
- Heartbeat y detección online/offline.
- Catálogo de sincronizadores y asignación por agente.
- Intervalos configurables desde el centro.
- Scheduler local en el agente.
- Comandos remotos seguros: `run_now`, `stop_run`, `pause_sync`, `resume_sync`, `refresh_config`.
- Una única ruta de ejecución mediante `SyncRunner`.
- Registro local de success/error en `sync_success` y `sync_errors`.
- Telemetría central durable mediante outbox JSON e idempotencia.
- Historial de ejecuciones, eventos y auditoría.
- Dashboard React conectado a API real.
- Recuperación ante caída de red y reinicio de Windows.
- Pruebas piloto con 3 agentes y prueba de carga/soak con 100 agentes.

## 3. No objetivos del MVP

Quedan expresamente fuera:

- Escritura bidireccional hacia ERP.
- Resolución de conflictos multidireccional.
- CDC avanzado genérico.
- Microservicios.
- Kafka, RabbitMQ o Redis obligatorio.
- WebSockets o MQTT para agentes.
- Kubernetes.
- Docker en PCs cliente.
- Auto-update remoto del agente.
- Shell remoto arbitrario.
- Acceso directo del agente al MySQL central.
- Ingesta de toda la data de negocio en el centro de control. El centro recibe control, telemetría y resultados; la data sincronizada permanece en la BD BAPPS del cliente para este MVP.

## 4. Arquitectura final

```text
┌────────────────────────────── CENTRO BAPPS SYNC ─────────────────────────────┐
│                                                                             │
│  React + TypeScript + Vite                                                  │
│          │                                                                  │
│          ▼                                                                  │
│  Laravel REST API — monolito modular                                        │
│          │                                                                  │
│          ▼                                                                  │
│  MySQL central                                                              │
│  clients · agents · sync_catalog · agent_syncs · sync_commands              │
│  sync_runs · sync_events · sync_audit_events                                │
│                                                                             │
└───────────────────────────────▲─────────────────────────────────────────────┘
                                │ HTTPS saliente
                                │ polling + heartbeat + eventos
                                │
┌───────────────────────────────┴─────────────────────────────────────────────┐
│                        PC / SERVIDOR DEL CLIENTE                            │
│                                                                             │
│  BAPPS Sync Agent — servicio Windows Python                                │
│  ├── AgentService                                                          │
│  ├── CommandPoller / CommandHandler                                        │
│  ├── Scheduler                                                              │
│  ├── SyncRunner                                                             │
│  ├── SynchronizerRegistry                                                   │
│  ├── Outbox                                                                 │
│  └── LocalSyncLogRepository                                                 │
│          │                                                                  │
│          ▼                                                                  │
│  Sincronizadores: clientes_valery, productos_valery, ventas_profit, ...    │
│          │                                                                  │
│          ▼                                                                  │
│  ERP/administrativo local → BD BAPPS del cliente                           │
│                              ├── datos sincronizados                        │
│                              ├── sync_success                               │
│                              └── sync_errors                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 5. Responsabilidades

### 5.1 Centro Laravel

- Autenticar usuarios y agentes.
- Mantener clientes, agentes, catálogo y asignaciones.
- Definir intervalos y estados `enabled/paused/disabled`.
- Crear comandos.
- Entregar comandos únicamente al agente correcto.
- Administrar lease, expiración e idempotencia de comandos.
- Recibir heartbeats y eventos.
- Aplicar idempotencia por `event_id`.
- Proyectar eventos a `sync_runs`, auditoría y métricas.
- Exponer APIs para React.

### 5.2 Agente Python

- Arrancar con Windows.
- Mantener una única instancia por máquina.
- Identificarse y enviar heartbeats.
- Consultar y reclamar comandos.
- Cachear la última configuración válida.
- Ejecutar scheduler local.
- Ejecutar `run_now` por la misma ruta que el scheduler.
- Detener cooperativamente una ejecución concreta.
- Escribir `sync_success` y `sync_errors`.
- Persistir eventos críticos antes de depender de la red.
- Reintentar entrega con backoff y jitter.
- No morir por el fallo de un sincronizador.

### 5.3 Sincronizador individual

Debe:

- Leer origen.
- Transformar si corresponde.
- Escribir destino.
- Consultar `context.raise_if_stopped()` en puntos seguros.
- Devolver `SyncResult`.

No debe:

- Hacer polling.
- Enviar heartbeat.
- Crear comandos.
- Conocer Laravel.
- Gestionar outbox.
- Decidir estados globales.
- Escribir directamente auditoría central.

## 6. Decisiones definitivas

| Tema | Decisión |
|---|---|
| Centro | Laravel monolítico modular + MySQL central + API REST JSON versionada. |
| Frontend | React + TypeScript + Vite + React Router + TanStack Query. |
| Agente | Python empaquetado como servicio Windows, un único agente por máquina. |
| Comunicación | HTTPS saliente iniciada por el agente. Sin puertos entrantes y sin acceso directo al MySQL central. |
| Control remoto | Polling de comandos cada 5 s con jitter; heartbeat cada 30 s con jitter. |
| Scheduler | Local en el agente. Laravel es la fuente de verdad de configuración e intervalos. |
| Comandos MVP | run_now, stop_run, pause_sync, resume_sync, refresh_config. |
| Comandos seguros | Whitelist, expiración, claim con lease, idempotencia por command_id/idempotency_key. |
| Ejecución | Scheduler y run_now entran al mismo SyncRunner. |
| Concurrencia inicial | Máximo 1 ejecución simultánea por agente en V1; lock por sync_code. |
| Detención | Cancelación cooperativa mediante stop_event; nunca matar threads arbitrariamente. |
| Schedules perdidos | Coalescing: máximo una ejecución catch-up por sync_code al volver. |
| Logs locales | El agente escribe resultados en las tablas existentes sync_success y sync_errors de la BD BAPPS del cliente. |
| Telemetría central | Outbox JSON durable; el evento central es fuente de verdad para observabilidad central. |
| No objetivos | Sin microservicios, Kafka, RabbitMQ, Redis obligatorio, WebSockets, MQTT, Kubernetes ni auto-update remoto en MVP. |
| Escala objetivo | Piloto con 3 agentes; diseño y prueba de carga para 100 agentes. |

## 7. Regla de KISS

No añadir una abstracción, servicio o infraestructura sin un segundo caso real o una métrica que lo justifique. Las interfaces se usan en fronteras estables: sincronizador, repositorio de logs, transporte API y outbox. No se creará una jerarquía extensa de factories o repositories por defecto.

## 8. Riesgos principales que el diseño ya mitiga

- Duplicados por respuesta perdida → `event_id` único e idempotencia.
- Comando reclamado y agente caído → lease + journal local.
- 100 agentes golpeando simultáneamente → jitter.
- Reconexión masiva tras caída → backoff exponencial + jitter.
- Scheduler bloqueando control remoto → control loop separado del worker.
- Acumulación infinita de schedules atrasados → coalescing.
- Dos instancias del agente → single-instance lock.
- Reinicio durante una ejecución → reconciliación y `interrupted`.
- BD del cliente caída y no se puede escribir `sync_errors` → outbox/agent log independiente.

## 9. Primera vertical slice obligatoria

No se debe empezar por el dashboard completo. La primera demostración funcional debe cubrir:

1. Crear agente en Laravel.
2. Enrolar agente Python.
3. Heartbeat visible.
4. Asignar `clientes_valery` con intervalo.
5. El agente descarga configuración.
6. `run_now` desde React/Laravel.
7. El agente reclama el comando.
8. `SyncRunner` ejecuta el sincronizador real.
9. Escribe `sync_success` o `sync_errors`.
10. Persiste evento en outbox.
11. Laravel recibe evento de forma idempotente.
12. React muestra el resultado.
13. `stop_run` funciona en una ejecución suficientemente larga.

Hasta que esto funcione, no se expande el catálogo.


---

# 02 — Diseño del BAPPS Sync Agent en Python

**Versión:** 1.1  
**Objetivo:** especificación implementable del agente Windows.

## 1. Principio de diseño

> Un servicio Windows, un control loop, un worker inicial, un `SyncRunner`, un registry de sincronizadores y una outbox durable.

## 2. Estructura de código aprobada

```text
bapps_sync_agent/
├── pyproject.toml
├── src/bapps_sync_agent/
│   ├── main.py
│   ├── application/
│   │   ├── agent_service.py
│   │   ├── command_poller.py
│   │   ├── command_handler.py
│   │   ├── scheduler.py
│   │   └── sync_runner.py
│   ├── domain/
│   │   ├── commands.py
│   │   ├── runs.py
│   │   ├── results.py
│   │   ├── errors.py
│   │   └── enums.py
│   ├── infrastructure/
│   │   ├── api_client.py
│   │   ├── outbox.py
│   │   ├── command_journal.py
│   │   ├── config_store.py
│   │   ├── local_sync_log_repository.py
│   │   ├── structured_logger.py
│   │   └── single_instance_lock.py
│   ├── connectors/
│   │   ├── firebird.py
│   │   ├── sqlserver.py
│   │   └── mysql.py
│   └── syncs/
│       ├── clientes_valery.py
│       ├── productos_valery.py
│       └── ...
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## 3. Dependencias e inyección

Se usará inyección explícita por constructor, sin contenedor DI externo.

```python
registry = SynchronizerRegistry({
    "clientes_valery": ClientesValerySynchronizer(
        source=FirebirdConnector(source_config),
        target=BappsClientDatabase(target_config),
    ),
})

runner = SyncRunner(
    registry=registry,
    log_repository=LocalSyncLogRepository(target_config),
    event_reporter=OutboxEventReporter(outbox),
    clock=SystemClock(),
)

agent = AgentService(
    api_client=ApiClient(api_config),
    command_handler=CommandHandler(runner, config_manager),
    scheduler=Scheduler(runner, config_manager),
    outbox=outbox,
)
```

## 4. Control loop

El control loop no ejecuta el trabajo pesado directamente.

```python
while not service_stop_event.is_set():
    recover_stale_outbox_items_if_due()
    flush_outbox_if_due()
    poll_commands_if_due()
    send_heartbeat_if_due()
    refresh_config_if_needed()
    scheduler.tick()
    sleep(1)
```

Frecuencias iniciales:

| Operación | Frecuencia |
|---|---:|
| Tick local | 1 s |
| Polling comandos | 5 s + jitter |
| Heartbeat | 30 s + jitter |
| Descarga config | Solo si versión remota cambia |
| Flush outbox | Inmediato cuando hay eventos + retry/backoff |

## 5. Worker y concurrencia

V1 usa `ThreadPoolExecutor(max_workers=1)` para que el agente siga atendiendo comandos y heartbeat mientras un sync corre, pero evitando carga paralela no medida sobre las bases del cliente.

Reglas:

- Un worker por agente inicialmente.
- Un mismo `sync_code` nunca se ejecuta dos veces simultáneamente.
- Por `sync_code`, máximo una intención pendiente coalescida.
- `run_now` y scheduler compiten por la misma cola y las mismas reglas.
- Aumentar a `max_workers=2` requiere métricas reales y pruebas de concurrencia.

## 6. SyncRunner

Responsabilidades exactas:

1. Validar que existe el `sync_code`.
2. Validar capacidad local.
3. Validar autorización/configuración.
4. Validar estado del sync.
5. Adquirir lock por `sync_code`.
6. Crear `run_id` y `correlation_id`.
7. Registrar la ejecución activa.
8. Emitir/persistir `run_started`.
9. Invocar al sincronizador.
10. Capturar `SyncInterrupted` por stop cooperativo.
11. Clasificar errores.
12. Construir `SyncResult`.
13. Persistir evento final en outbox.
14. Escribir `sync_success` o `sync_errors` cuando corresponda.
15. Liberar locks y estado activo.

Pseudocódigo:

```python
def execute(sync_code: str, trigger: Trigger, command_id: str | None = None):
    validate(sync_code)

    with lock_manager.acquire(sync_code):
        run = ActiveRun.create(sync_code=sync_code, trigger=trigger)
        active_runs.add(run)

        outbox.persist(Event.run_started(run))

        try:
            result = registry.resolve(sync_code).run(run.context)
            final_status = RunStatus.SUCCESS
        except SyncInterrupted:
            result = SyncResult.interrupted()
            final_status = RunStatus.INTERRUPTED
        except Exception as exc:
            result = error_classifier.to_result(exc)
            final_status = RunStatus.FAILED

        final_event = Event.run_finished(run, result, final_status)
        outbox.persist(final_event)

        if final_status is RunStatus.SUCCESS:
            log_repository.record_success(run, result)
        elif final_status is RunStatus.FAILED:
            log_repository.record_error(run, result)

        active_runs.remove(run.run_id)
        return result
```

## 7. SyncContext y cancelación cooperativa

```python
@dataclass(frozen=True)
class SyncContext:
    run_id: str
    correlation_id: str
    sync_code: str
    trigger: str
    stop_event: threading.Event

    def should_stop(self) -> bool:
        return self.stop_event.is_set()

    def raise_if_stopped(self) -> None:
        if self.should_stop():
            raise SyncInterrupted()
```

Los sincronizadores deben comprobar la cancelación:

- Antes de una consulta pesada cuando el driver lo permita.
- Después de recuperar un lote.
- Antes de escribir un lote.
- Después del commit de un lote.

No se promete detención instantánea durante una llamada bloqueante del driver. Por eso existe el estado `stopping`.

## 8. Semántica de comandos

### run_now

- Ejecuta una ejecución inmediatamente si el sync existe, está autorizado y no está ya corriendo.
- Si está `paused`, política MVP: `run_now` requiere `allow_manual_when_paused=true` explícito; por defecto se rechaza con `SYNC_PAUSED`.

### pause_sync

- Impide ejecuciones futuras automáticas y manuales por defecto.
- No detiene una ejecución ya activa.

### resume_sync

- Reactiva futuras ejecuciones.
- No crea backlog retroactivo.

### stop_run

- Apunta a un `run_id` concreto.
- Cambia a `stopping` y activa `stop_event`.
- Si la ejecución ya terminó, devuelve `skipped: RUN_NOT_ACTIVE`.
- Dos stops iguales son idempotentes.

### refresh_config

- Fuerza descarga de la configuración más reciente.

## 9. Scheduler

Se usa calendario fijo por intervalos, no `finished_at + interval`.

Ejemplo 15 min:

```text
10:00 · 10:15 · 10:30 · 10:45
```

Reglas:

- El agente calcula slots por UTC.
- Al cambiar intervalo, recalcula el próximo slot futuro.
- Si el agente estuvo offline y perdió varios slots, aplica coalescing: máximo una ejecución catch-up.
- Si el mismo sync sigue running al llegar el siguiente slot, se registra `skipped: SYNC_ALREADY_RUNNING` o se coalesce una sola intención, según la política del sync. MVP recomendado: coalescer una intención y no crear múltiples pendientes.
- El cambio de hora/DST no afecta porque el scheduler usa UTC.

## 10. Capacidad del worker

Para cada agente debe medirse:

```text
utilización = Σ(duración_p95_del_sync / intervalo_del_sync)
```

Con un worker:

- objetivo normal: < 0,70
- warning: 0,70–0,90
- crítico: > 0,90
- imposible de sostener: >= 1,00 de forma continua

## 11. Estado local mínimo

No se instala MySQL ni SQLite adicional. Se usan archivos:

```text
C:/ProgramData/Bapps/SyncAgent/
├── config/
│   ├── agent-identity.json
│   └── active-config.json
├── state/
│   ├── command-journal.json
│   └── last-run-state.json
├── outbox/
│   ├── pending/
│   ├── sending/
│   └── failed/
├── logs/
└── locks/
```

Es importante distinguir esto de la BD BAPPS del cliente: el agente sí se conecta a esa BD existente para sincronizar datos y escribir `sync_success`/`sync_errors`; simplemente no instala una base propia para su estado interno.

## 12. Command journal

Propósito: evitar reejecutar un comando ya completado cuando la respuesta se perdió.

Contenido mínimo:

```json
{
  "CMD-5001": {
    "status": "completed",
    "run_id": "RUN-20260715-000142",
    "completed_at": "2026-07-15T18:20:31Z"
  }
}
```

Política:

- Escritura atómica.
- Retención configurable, inicialmente 30 días o 10.000 entradas, lo que ocurra primero.
- Si llega un comando conocido, no se reejecuta; se responde con el resultado previo disponible.

## 13. Outbox

Estados físicos:

```text
pending -> sending -> ACK válido -> eliminar
                 +-> retryable -> pending
                 +-> permanente -> failed
```

Reglas:

- Un evento por archivo.
- `event_id` UUID/ULID único.
- Escritura temporal + rename atómico.
- Al arrancar, `sending/` se recupera a `pending/` si quedó huérfano.
- Un JSON corrupto pasa a `failed/` sin bloquear el resto.
- Backoff exponencial con jitter.
- Si no se puede persistir un evento crítico por disco/permisos, no iniciar nuevas ejecuciones críticas hasta recuperar capacidad.

## 14. Logs locales sync_success y sync_errors

El agente es el único responsable de escribir estos resultados desde `LocalSyncLogRepository`.

Campos existentes de referencia:

```text
id
 datetime
mysql_table
sqlserver_table
operation
message
```

Reglas:

- `success` → `sync_success`.
- `failed` → `sync_errors`.
- `interrupted` por orden humana no se registra como error por defecto; queda en log estructurado y evento central. Si la compatibilidad legacy exige registrar todo desenlace, usar operación explícita `INTERRUPTED_BY_COMMAND`, nunca disfrazarlo como fallo técnico.
- Si la BD BAPPS del cliente está caída, puede ser imposible escribir `sync_errors`; el agente debe conservar el error en outbox/log estructurado y reportarlo al centro cuando sea posible.

## 15. Single-instance lock

Debe impedir dos servicios simultáneos por agente/máquina. En Windows se recomienda mutex global o lock equivalente.

Segundo proceso:

```text
Detecta instancia existente → log AGENT_ALREADY_RUNNING → termina
```

## 16. Recuperación tras crash/reinicio

Al iniciar:

1. Adquirir single-instance lock.
2. Cargar identidad.
3. Cargar última config válida.
4. Recuperar outbox `sending/`.
5. Detectar locks huérfanos.
6. Detectar ejecución anterior inconclusa.
7. Emitir `interrupted` con `AGENT_RESTARTED` cuando corresponda.
8. Enviar heartbeat.
9. Retomar scheduler sin reproducir todos los slots perdidos.

## 17. Criterios de aceptación del agente

- El control loop no se bloquea por una ejecución larga.
- `stop_run` se procesa mientras un sync corre.
- Reinicio no deja runs eternamente `running`.
- Comando duplicado no crea una segunda ejecución.
- Evento duplicado no duplica efectos centrales.
- API caída no detiene schedules autorizados.
- Un sync con excepción no derriba el servicio.
- El mismo `sync_code` no corre simultáneamente dos veces.
- Outbox sobrevive crash.
- Jitter evita sincronización masiva de polling.


---

# 03 — Centro Laravel, API y frontend

**Versión:** 1.1

## 1. Arquitectura del centro

Laravel será un monolito modular. Una sola aplicación desplegable, con límites internos claros.

```text
app/
├── Domains/
│   ├── Clients/
│   ├── Agents/
│   ├── SyncCatalog/
│   ├── AgentSyncs/
│   ├── Commands/
│   ├── Runs/
│   ├── Events/
│   ├── Audit/
│   └── Security/
├── Http/
│   ├── Controllers/
│   │   ├── AgentApi/
│   │   └── ControlApi/
│   ├── Requests/
│   ├── Resources/
│   └── Middleware/
└── Jobs/
```

No se usará repository pattern en todos los modelos por defecto. Los controllers deben ser delgados; los casos de uso viven en Actions/Services.

## 2. Dos superficies de API

### 2.1 API del agente

Autenticación máquina-a-máquina por credencial individual.

```text
POST /api/v1/agent/enroll
POST /api/v1/agent/heartbeat
GET  /api/v1/agent/config
POST /api/v1/agent/commands/claim
POST /api/v1/agent/commands/{command_id}/result
POST /api/v1/agent/events
```

### 2.2 API del centro de control

```text
POST   /api/v1/auth/login
GET    /api/v1/dashboard/metrics
GET    /api/v1/agents
GET    /api/v1/agents/{code}
POST   /api/v1/agents/{code}/commands
PATCH  /api/v1/agents/{code}/syncs/{sync_code}
GET    /api/v1/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/retry
GET    /api/v1/audit
GET    /api/v1/clients
GET    /api/v1/clients/{id}
GET    /api/v1/syncs
POST   /api/v1/syncs
PATCH  /api/v1/syncs/{code}
```

## 3. Claim de comandos

No se recomienda un `GET` con efecto lateral. El agente reclama comandos con:

```text
POST /api/v1/agent/commands/claim
```

Request:

```json
{
  "agent_code": "AGT-000142",
  "max_commands": 5,
  "known_command_ids": ["CMD-5001"]
}
```

Response:

```json
{
  "data": [
    {
      "schema_version": "1.0",
      "command_id": "CMD-5002",
      "type": "run_now",
      "issued_at": "2026-07-15T18:00:00Z",
      "expires_at": "2026-07-15T18:10:00Z",
      "lease_expires_at": "2026-07-15T18:02:00Z",
      "idempotency_key": "idem-...",
      "payload": {
        "sync_code": "clientes_valery"
      }
    }
  ]
}
```

Reglas transaccionales del claim:

- Solo comandos `pending` y no expirados.
- Solo del agente autenticado.
- Cambiar a `claimed` en la misma transacción.
- Registrar `claimed_at` y `lease_expires_at`.
- Limitar cantidad.
- Ordenar por `created_at ASC`.
- Índice compuesto por patrón de consulta.

Si vence lease sin resultado, el comando puede volver a `pending`, pero el agente debe protegerse con el journal local para no repetir un comando ya completado.

## 4. Resultado de comando

```text
POST /api/v1/agent/commands/{command_id}/result
```

Ejemplo:

```json
{
  "status": "completed",
  "completed_at": "2026-07-15T18:00:14Z",
  "result": {
    "run_id": "RUN-20260715-000142"
  }
}
```

Validaciones:

- command pertenece al agente autenticado.
- transición válida.
- idempotencia: repetir el mismo resultado no produce efectos adicionales.

## 5. Heartbeat

Request:

```json
{
  "schema_version": "1.0",
  "agent_code": "AGT-000142",
  "agent_version": "1.0.0",
  "config_version": 18,
  "machine_name": "SERVER-VALERY",
  "status": "online",
  "running_runs": [
    {
      "run_id": "RUN-20260715-000142",
      "sync_code": "clientes_valery",
      "status": "running",
      "started_at": "2026-07-15T17:55:00Z"
    }
  ],
  "outbox": {
    "pending_count": 3,
    "pending_bytes": 8120
  }
}
```

Response:

```json
{
  "acknowledged": true,
  "latest_config_version": 19,
  "has_pending_commands": true,
  "server_time": "2026-07-15T18:00:00Z"
}
```

## 6. Configuración

El centro es fuente de verdad. El agente conserva la última versión válida.

```json
{
  "schema_version": "1.0",
  "version": 19,
  "agent_code": "AGT-000142",
  "syncs": [
    {
      "code": "clientes_valery",
      "status": "enabled",
      "interval_seconds": 900,
      "config": {}
    },
    {
      "code": "ventas_valery",
      "status": "paused",
      "interval_seconds": 14400,
      "config": {}
    }
  ]
}
```

No enviar secretos innecesarios. Los secretos locales deben resolverse por mecanismo seguro de instalación/config local cuando sea posible.

## 7. Ingesta de eventos

```text
POST /api/v1/agent/events
```

Reglas P0:

- `event_id` único.
- Validar `agent_code` contra autenticación.
- Repetir evento ya procesado devuelve ACK lógico exitoso.
- Soportar eventos fuera de orden.
- `run_finished` puede llegar antes de `run_started`; la proyección no debe retroceder un estado terminal a `running`.
- Persistir evento bruto y luego proyectar.

## 8. Frontend definitivo

```text
React
TypeScript
Vite
React Router
TanStack Query
```

Estructura:

```text
src/
├── app/
├── api/
├── features/
│   ├── dashboard/
│   ├── agents/
│   ├── runs/
│   ├── commands/
│   ├── audit/
│   ├── clients/
│   └── syncs/
├── components/
│   ├── ui/
│   └── layout/
└── lib/
    ├── statuses.ts
    ├── errors.ts
    ├── dates.ts
    └── formatters.ts
```

No Redux inicialmente. TanStack Query maneja estado remoto; estado local se limita a drawers, filtros, tabs y modales.

## 9. Polling en frontend

Sugerencia inicial:

| Dato | Frecuencia |
|---|---:|
| Dashboard | 15 s |
| Runs visibles `running/stopping` | 5–10 s |
| Estado de comando recién emitido | 5 s hasta terminal |
| Lista de agentes | manual + 30 s si la operación lo requiere |

Esto es polling de UI y es independiente del polling del agente.

## 10. Seguridad y tenancy

- Cada agente solo ve su configuración y comandos.
- Cada evento se vincula al agente autenticado, no se confía ciegamente en `agent_code` del payload.
- RBAC para usuarios.
- Auditoría de comandos y cambios de config.
- Rate limiting primario por credencial/agent_id; protección secundaria por IP.
- HTTPS obligatorio.
- No registrar secretos completos.

## 11. Manejo de 100 agentes

Con 100 agentes, polling cada 5 s y heartbeat cada 30 s producen aproximadamente 23,3 req/s promedio en steady state. No justifica microservicios. Sí exige:

- índices correctos,
- jitter,
- timeouts,
- pool de conexiones bien dimensionado,
- pruebas de carga,
- evitar N+1,
- respuestas pequeñas,
- paginación,
- retención de eventos.


---

# 04 — Contratos, enums y máquinas de estado

**Versión:** 1.1

## 1. Regla

Los contratos versionados son la interfaz entre Python, Laravel y React. Los JSON Schema de referencia están en `contracts/`.

## 2. Identificadores

- `agent_code`: estable, único, formato `AGT-...`.
- `command_id`: UUID/ULID o identificador único prefijado `CMD-...`.
- `run_id`: único `RUN-...`.
- `correlation_id`: agrupa eventos de una ejecución.
- `event_id`: único globalmente; clave de idempotencia de eventos.
- `idempotency_key`: única por comando semántico.

## 3. Enums

### AgentStatus

```text
online
offline
enrolled
disabled
```

### SyncStatus

```text
enabled
paused
disabled
```

### RunStatus

```text
pending
running
stopping
success
failed
interrupted
skipped
```

### CommandStatus

```text
pending
claimed
completed
failed
skipped
expired
```

### CommandType

```text
run_now
stop_run
pause_sync
resume_sync
refresh_config
```

### TriggerType

```text
schedule
command
manual
```

## 4. Máquina de estados de run

```text
pending
   │
   ▼
running ───────────────► success
   │ ├─────────────────► failed
   │ └──── stop ───────► stopping ─────► interrupted
   │
   └──── condición ────► skipped
```

Reglas:

- Estados terminales: `success`, `failed`, `interrupted`, `skipped`.
- No se retrocede de terminal a `running` por evento tardío.
- Reintento crea un nuevo `run_id`.
- `stopping` es transitorio y solo aplica a una ejecución activa.

## 5. Máquina de estados de comando

```text
pending ── claim ──► claimed ──► completed
   │                   ├────────► failed
   │                   ├────────► skipped
   │                   └ lease vencida ─► pending
   └ expiración ──────► expired
```

Reglas:

- Un comando expirado nunca se ejecuta.
- Resultado duplicado es idempotente.
- El command journal evita repetir efecto local.

## 6. Semántica exacta por comando

| Comando | Payload | Efecto | Idempotencia |
|---|---|---|---|
| run_now | sync_code | Intenta iniciar ejecución | mismo command_id no inicia dos runs |
| stop_run | run_id | Solicita stop cooperativo | segundo stop no duplica efecto |
| pause_sync | sync_code | Bloquea futuras ejecuciones | pausar ya pausado = completed/skipped definido |
| resume_sync | sync_code | Reactiva futuras ejecuciones | reanudar activo es idempotente |
| refresh_config | vacío | Fuerza refresh | repetir es seguro |

## 7. Códigos de error MVP

```text
SOURCE_CONNECTION_FAILED
TARGET_CONNECTION_FAILED
CENTRAL_API_UNAVAILABLE
SYNC_ALREADY_RUNNING
SYNC_NOT_FOUND
SYNC_NOT_AUTHORIZED
SYNC_PAUSED
RUN_NOT_ACTIVE
COMMAND_EXPIRED
AUTHENTICATION_FAILED
INVALID_CONFIG
SCHEMA_CHANGED
OUTBOX_WRITE_FAILED
OUTBOX_EVENT_CORRUPT
AGENT_RESTARTED
AGENT_ALREADY_RUNNING
LOCAL_LOG_WRITE_FAILED
```

Cada código debe definir:

- `retryable` boolean.
- mensaje técnico.
- mensaje operativo para UI.
- acción sugerida.

## 8. Entrega y consistencia

### Comandos

Semántica: **at-least-once delivery con efecto idempotente**.

### Eventos

Semántica: **at-least-once delivery + idempotencia de servidor por event_id**.

### Data del sincronizador

Cada sincronizador debe documentar su propia idempotencia: clave funcional, estrategia upsert, deletes y reejecución.

## 9. Eventos mínimos

```text
agent_started
heartbeat
run_started
run_finished
sync_error
command_claimed
command_completed
config_applied
outbox_warning
```

Para KISS, el centro puede persistir solo los necesarios para trazabilidad del MVP: `run_started`, `run_finished`, `sync_error` y eventos de comando/auditoría. No crear un event sourcing completo.

## 10. Ejemplo de run_finished

```json
{
  "schema_version": "1.0",
  "event_id": "EVT-01J...",
  "event_type": "run_finished",
  "agent_code": "AGT-000142",
  "run_id": "RUN-20260715-000142",
  "correlation_id": "CORR-01J...",
  "sync_code": "clientes_valery",
  "occurred_at": "2026-07-15T18:20:31Z",
  "payload": {
    "status": "success",
    "trigger": "command",
    "rows_read": 1240,
    "rows_inserted": 900,
    "rows_updated": 340,
    "rows_deleted": 0,
    "rows_failed": 0,
    "duration_ms": 8120,
    "error_code": null,
    "error_message": null
  }
}
```

## 11. Compatibilidad de versiones

- Contratos llevan `schema_version`.
- API usa `/api/v1`.
- El agente informa `agent_version`.
- Laravel puede mantener un `min_supported_agent_version`.
- Nunca romper un agente desplegado cambiando silenciosamente nombres o tipos de campos.


---

# 05 — Modelo de datos y migraciones

**Versión:** 1.1

## 1. Tablas centrales mínimas

```text
clients
agents
sync_catalog
agent_syncs
sync_commands
sync_runs
sync_events
sync_audit_events
users / auth
```

Se usa `agent_syncs` porque la asignación operativa y el scheduler pertenecen a un agente concreto. El cliente se deriva por relación con `agents.client_id`.

## 2. clients

Campos sugeridos:

```text
id
name
system_type
status
timezone nullable
created_at
updated_at
```

## 3. agents

```text
id
client_id
agent_code UNIQUE
machine_name
os
version
status
last_seen_at
last_ip
enabled
credential_hash
config_version
created_at
updated_at
```

Índices:

```text
UNIQUE(agent_code)
INDEX(status, last_seen_at)
INDEX(client_id, status)
```

## 4. sync_catalog

```text
id
code UNIQUE
functional_key
name
source_type
min_agent_version
enabled_globally
default_interval_seconds
description
created_at
updated_at
```

## 5. agent_syncs

```text
id
agent_id
sync_catalog_id
status                enabled|paused|disabled
interval_seconds
config_version
config_json
next_run_hint nullable
created_at
updated_at
```

Constraint:

```text
UNIQUE(agent_id, sync_catalog_id)
```

No mantener simultáneamente `enabled BOOLEAN` y `status`; una única fuente de verdad evita contradicción.

## 6. sync_commands

```text
id
command_id UNIQUE
agent_id
command_type
sync_code nullable
run_id nullable
payload_json nullable
status
idempotency_key UNIQUE
created_by nullable
issued_at
expires_at
claimed_at nullable
lease_expires_at nullable
completed_at nullable
result_json nullable
created_at
updated_at
```

Índice crítico:

```text
INDEX(agent_id, status, expires_at, created_at)
```

## 7. sync_runs

```text
id
run_id UNIQUE
agent_id
client_id
sync_catalog_id
correlation_id
status
trigger
command_id nullable
started_at
finished_at nullable
duration_ms nullable
rows_read
rows_inserted
rows_updated
rows_deleted
rows_failed
error_code nullable
error_message nullable
agent_version
created_at
updated_at
```

Índices:

```text
UNIQUE(run_id)
INDEX(agent_id, started_at)
INDEX(client_id, started_at)
INDEX(status, started_at)
INDEX(sync_catalog_id, started_at)
```

## 8. sync_events

```text
id
event_id UNIQUE
schema_version
event_type
agent_id
client_id
sync_code nullable
run_id nullable
correlation_id nullable
occurred_at
received_at
payload_json
created_at
```

Índices:

```text
UNIQUE(event_id)
INDEX(agent_id, occurred_at)
INDEX(run_id)
INDEX(event_type, occurred_at)
```

## 9. sync_audit_events

Registra acciones humanas y cambios sensibles:

```text
id
kind
action
actor_type
actor_id nullable
target_type
target_id
result
context_json
occurred_at
created_at
```

Auditar como mínimo:

- crear comando,
- pausar/reanudar sync,
- cambiar intervalo,
- enrolar/deshabilitar agente,
- login administrativo relevante.

## 10. Logs locales existentes

La BD BAPPS del cliente ya dispone de:

```text
sync_success(id, datetime, mysql_table, sqlserver_table, operation, message)
sync_errors(id, datetime, mysql_table, sqlserver_table, operation, message)
```

No se replican como fuente de verdad central. El agente escribe en ellas para compatibilidad y operación local, mientras `sync_events`/`sync_runs` representan la trazabilidad central.

## 11. Retención

Política inicial propuesta:

- `sync_runs`: 12 meses online; revisar según volumen.
- `sync_events`: 90 días online para payload bruto; luego archivar o podar según necesidad.
- `sync_audit_events`: mínimo 12 meses; sujeto a política de negocio.
- Comandos terminales: 90 días o más si auditoría lo requiere.

No implementar archivado complejo en la primera semana. Sí dejar fechas, índices y jobs de pruning preparados.

## 12. Migraciones y constraints P0

Obligatorio antes de piloto:

- UNIQUE event_id.
- UNIQUE command_id.
- UNIQUE idempotency_key.
- UNIQUE run_id.
- UNIQUE agent_code.
- FK correctas.
- Índices de polling y listados.
- Tests de duplicados y cross-agent.


---

# 06 — Estrategia QA del MVP

**Versión:** 1.1  
**Rol:** Gate de calidad antes de piloto y antes de 100 agentes.

## 1. Política de severidad

### P0 — Bloqueante

Puede causar pérdida silenciosa, duplicado funcional, ejecución incorrecta, acceso cross-tenant, corrupción o incapacidad de recuperación.

### P1 — Alta

Degrada operación, observabilidad o confiabilidad, pero existe recuperación manual razonable.

### P2 — Media

Problema de UX, diagnóstico o eficiencia sin riesgo inmediato de datos.

## 2. P0 obligatorios

1. `event_id` duplicado no duplica efectos.
2. Comando duplicado no crea una segunda ejecución.
3. Comando claimed con agente caído se recupera mediante lease.
4. Reinicio durante ejecución no deja run eternamente `running`.
5. Reinicio durante escritura outbox no pierde ni corrompe silenciosamente el evento.
6. Scheduler + run_now simultáneos no ejecutan dos veces el mismo sync.
7. stop_run + finalización simultánea produce un único estado terminal coherente.
8. Agente incorrecto no puede reclamar comando ajeno.
9. Evento de otro agente/cliente se rechaza.
10. API caída no detiene schedules locales autorizados.
11. Reconexión no crea tormenta sincronizada sin backoff/jitter.
12. Disco lleno/outbox no disponible se detecta y bloquea nuevas ejecuciones críticas según política.
13. BD BAPPS caída no elimina la capacidad de reportar el error central mediante outbox/log.
14. Dos instancias del agente no pueden operar simultáneamente.
15. Config corrupta no reemplaza última configuración válida.

## 3. Matriz funcional mínima

| Área | Casos obligatorios |
|---|---|
| Instalación | limpia, reinstalación, servicio auto-start, permisos, doble instancia |
| Enrolamiento | token válido, inválido, usado, expirado, agente disabled |
| Heartbeat | OK, timeout, 401, 403, 429, 500, reloj desviado, payload inválido |
| Config | primera, sin cambio, nueva versión, JSON inválido, sync desconocido, intervalo inválido |
| Scheduler | 15 min, 4 h, coincidencias, pausa, reinicio, missed schedules, DST/UTC |
| run_now | normal, duplicado, expirado, inexistente, no autorizado, paused, ya running |
| stop_run | normal, duplicado, terminado, inexistente, otro agente, durante query y batch |
| pause/resume | idempotencia, ejecución activa, no backlog retroactivo |
| SyncRunner | success, error origen, error destino, excepción inesperada, lock, métricas |
| sync_success | insert OK, DB caída, timeout, caracteres especiales, commit con respuesta perdida |
| sync_errors | mismos casos + error que impide escribir en la propia tabla |
| Outbox | ACK, retry, pérdida de respuesta, corrupto, disco lleno, permisos, crash |
| Eventos | duplicado, fuera de orden, payload inválido, run inexistente, cross-agent |
| Reinicios | idle, running, stopping, outbox write, HTTP send, config update |
| Red | DNS, connect timeout, read timeout, TLS, intermitencia, 429, 5xx |
| Seguridad | token robado, replay, comando expirado, payload gigante, secretos en logs |
| Frontend | loading, empty, error, retry, pending, expired, failed, stopping, offline |

## 4. Tests unitarios del agente

- `SyncContext.raise_if_stopped`.
- Transiciones de run.
- Transiciones de comando.
- Scheduler de slots fijos.
- Coalescing de missed schedules.
- Lock por sync_code.
- Single-instance lock.
- Backoff + jitter.
- Serialización de eventos.
- Escritura atómica outbox.
- Recuperación de `sending/`.
- JSON corrupto.
- Command journal idempotente.
- ErrorClassifier.
- Validación config.

## 5. Tests de integración del agente

- Firebird real/controlado disponible y caído.
- SQL Server cuando se incorpore Profit.
- BD BAPPS disponible y caída.
- Laravel disponible y caída.
- Respuesta HTTP perdida después del commit.
- Reinicio del proceso durante diferentes etapas.
- `stop_run` con sincronizador real que procesa por lotes.

## 6. Tests Laravel

- Claim transaccional de comandos.
- Dos claims concurrentes no entregan mismo comando dos veces sin control de lease.
- Expiración.
- Resultado duplicado.
- Event idempotency.
- Out-of-order projection.
- Cross-agent authorization.
- Constraints/unique keys.
- Paginación y filtros.
- Dashboard sin N+1.

## 7. Tests E2E

### E2E-01 éxito

```text
React → run_now → Laravel → claim → agente → clientes_valery
→ sync_success → outbox → Laravel → sync_runs → React
```

### E2E-02 error de origen

```text
Firebird caído → sync_errors + evento failed → UI muestra error operativo
```

### E2E-03 central offline

```text
Laravel offline → sync local continúa → outbox crece → Laravel vuelve → entrega eventual
```

### E2E-04 stop

```text
run larga → stop_run → stopping → punto seguro → interrupted
```

### E2E-05 duplicado

```text
servidor hace commit de EVT-123 → respuesta se pierde → reenvío EVT-123 → un solo efecto
```

## 8. Pruebas de carrera obligatorias

- Scheduler y run_now para el mismo sync en el mismo segundo.
- Dos run_now simultáneos.
- stop_run y success simultáneos.
- pause_sync y slot scheduler simultáneos.
- Cambio config mientras scheduler evalúa.
- Reinicio después de claim y antes de iniciar run.
- Reinicio después de finalizar y antes de reportar comando completed.

## 9. Pruebas de resiliencia

- Centro 30 min offline.
- Centro 24 h offline en un agente.
- 10.000 eventos pendientes.
- Outbox de 1 GB en entorno de prueba.
- Un archivo corrupto entre miles válidos.
- DNS intermitente.
- 429 sostenido.
- 500 alternante.
- 10 agentes reiniciándose aleatoriamente durante runs.

## 10. Criterios de aprobación del piloto de 3 agentes

- 7 días de operación sin pérdida crítica.
- 0 duplicados funcionales.
- 0 cross-tenant.
- 0 runs huérfanos indefinidos.
- 100% de comandos terminales con auditoría.
- Outbox recuperada tras caídas simuladas.
- stop_run probado en sync real.
- utilización del worker medida por agente.

## 11. Criterios de aprobación para 100 agentes

- 24 h de soak mínimo.
- 100 agentes simulados o reales.
- polling y heartbeat con jitter.
- p95 API control < 300 ms como objetivo inicial.
- p99 < 1 s como objetivo inicial.
- 5xx < 0,1% bajo carga objetivo.
- 0 eventos críticos perdidos.
- 0 duplicados funcionales.
- 99% de `run_now` recibido por agente online en < 10 s.
- reconnection storm absorbida sin caída prolongada.

Estos valores son objetivos de prueba, no garantías sin medición.


---

# 07 — Escalabilidad y operación con 100 agentes

**Versión:** 1.1

## 1. Respuesta directa

Sí: la arquitectura de polling sigue funcionando con 100 agentes. El polling es por agente, no por sincronizador.

Con:

```text
100 agentes
poll comandos cada 5 s
heartbeat cada 30 s
```

Carga promedio aproximada:

```text
comandos: 100 / 5  = 20 req/s
heartbeat: 100 / 30 = 3,33 req/s
total control plane ≈ 23,33 req/s
```

El número de sincronizadores por agente no multiplica este polling.

## 2. Riesgo real: thundering herd

Sin jitter:

```text
00:00:00 → 100 requests
00:00:05 → 100 requests
00:00:10 → 100 requests
```

Con jitter, cada agente tiene un desfase distinto. Es obligatorio en MVP.

## 3. Reconnection storm

Después de 30 minutos de caída central, 100 agentes pueden reconectar con outbox acumulada. Reglas:

- backoff exponencial,
- jitter,
- límite de eventos por flush,
- no vaciar 10.000 eventos en una única request,
- límites de payload,
- ACK por lote o evento según implementación elegida.

MVP recomendado: un evento por archivo local y endpoint que acepte pequeños lotes de eventos para eficiencia, preservando idempotencia individual por `event_id`.

## 4. 100 agentes con 4–10 sincronizadores

La capacidad de control central sigue siendo baja. La capacidad local depende de duración e intervalos.

Ejemplo de peor caso teórico:

```text
100 agentes × 10 syncs × 96 ejecuciones/día (cada 15 min)
= 96.000 runs/día
```

Con dos eventos por run:

```text
≈ 192.000 eventos/día
```

Eso exige retención e índices, pero no obliga a microservicios.

## 5. Índices críticos

```text
sync_commands(agent_id, status, expires_at, created_at)
sync_runs(agent_id, started_at)
sync_runs(status, started_at)
sync_events UNIQUE(event_id)
sync_events(agent_id, occurred_at)
agents(status, last_seen_at)
```

## 6. Qué medir desde el piloto

### Centro

- req/s.
- p50/p95/p99.
- 4xx/5xx.
- conexiones DB.
- slow queries.
- tamaño de tablas.
- jobs pendientes.

### Agente

- duración p50/p95 por sync.
- utilización del worker.
- latencia command claim → start.
- outbox pending count/bytes.
- reintentos.
- errores por código.
- tiempo desde evento local hasta ACK central.

## 7. Umbrales iniciales de outbox

Propuesta:

```text
warning:  1.000 eventos o 100 MB
critical: 10.000 eventos o 1 GB
```

Ajustar con datos reales.

## 8. Cuándo evaluar Redis

No por llegar a 100 agentes. Evaluar Redis si métricas muestran:

- database queue retrasada,
- locks/contadores de alta frecuencia,
- necesidad operativa de Horizon,
- latencia o throughput no resueltos con SQL/índices.

## 9. Cuándo evaluar long polling o WebSockets

No por defecto. Evaluar si:

- 5 s de latencia de comandos es inaceptable,
- la frecuencia de polling genera carga demostrada,
- existe un requisito real de comunicación sub-segundo.

Antes de WebSockets, considerar long polling.

## 10. Escala progresiva recomendada

```text
3 agentes    → piloto funcional
10 agentes   → validación operativa
30 agentes   → revisar métricas y tuning
100 agentes  → carga normal objetivo
500+ agentes → reevaluar con evidencia
```

La arquitectura debe poder evolucionar sin reescribir el agente porque los contratos están versionados y el centro está modularizado.


---

# 08 — Roadmap, backlog y orden de implementación

**Versión:** 1.1

## Principio

Cada fase debe producir una vertical slice verificable. No construir capas completas sin flujo real.

## Fase 0 — Congelar contratos y repositorios

**Objetivo:** evitar que Python, Laravel y React evolucionen con contratos distintos.

Tareas:

- [ ] Crear repositorio `bapps-sync-agent`.
- [ ] Crear repositorio `bapps-sync-center` o monorepo decidido por equipo.
- [ ] Incluir `contracts/` compartido o publicado como paquete/versionado.
- [ ] Aprobar enums y máquinas de estado.
- [ ] Aprobar payloads heartbeat/config/command/event.
- [ ] Crear CI básico.

Exit criteria:

- Los JSON Schema validan ejemplos correctos y rechazan ejemplos inválidos.
- No quedan enums contradictorios.

## Fase 1 — Núcleo mínimo del agente

Tareas:

- [ ] Scaffolding Python.
- [ ] Structured logging.
- [ ] ConfigStore atómico.
- [ ] SingleInstanceLock.
- [ ] Synchronizer protocol/interface mínima.
- [ ] SynchronizerRegistry.
- [ ] SyncResult.
- [ ] SyncContext + stop_event.
- [ ] SyncRunner.
- [ ] Worker `max_workers=1`.
- [ ] Tests unitarios.

Exit criteria:

- Un fake synchronizer puede correr, fallar y ser detenido sin bloquear control loop.

## Fase 2 — Outbox y recuperación

- [ ] pending/sending/failed.
- [ ] escritura atómica.
- [ ] event_id.
- [ ] recovery de sending.
- [ ] corrupt handling.
- [ ] backoff+jitter.
- [ ] límites y métricas.

Exit criteria:

- Crash simulado no pierde evento.

## Fase 3 — API Laravel para agentes

- [ ] Enroll.
- [ ] Auth por agente.
- [ ] Heartbeat.
- [ ] Config versionada.
- [ ] Command claim con lease.
- [ ] Command result.
- [ ] Event ingest idempotente.
- [ ] Migraciones e índices.
- [ ] Tests DB/API.

Exit criteria:

- Agente fake puede enrolar, hacer heartbeat, reclamar comando y reportar evento.

## Fase 4 — Integrar clientes_valery real

- [ ] Extraer lógica existente a `ClientesValerySynchronizer`.
- [ ] Inyectar connector Firebird y destino BAPPS.
- [ ] Implementar `SyncResult` real.
- [ ] Añadir puntos seguros de stop.
- [ ] Documentar idempotencia del sync.

Exit criteria:

- E2E real en entorno controlado.

## Fase 5 — Logs locales

- [x] `LocalSyncLogRepository`.
- [x] éxito → sync_success.
- [x] fallo → sync_errors.
- [x] fallback si DB local no disponible: el evento/outbox conserva la trazabilidad central.
- [x] tests unitarios de creación/commit y error; queda pendiente la prueba real de timeout/caída de MySQL.

Exit criteria:

- Cada success/failed real queda reflejado localmente y centralmente sin acoplar el sync al logging.

## Fase 6 — Scheduler y configuración

- [ ] Intervalos fijos UTC.
- [ ] cache última config válida.
- [ ] config_version en heartbeat.
- [ ] coalescing missed schedules.
- [ ] status enabled/paused/disabled.
- [ ] utilización del worker.

Exit criteria:

- Un agente puede operar 24 h con centro intermitente y mantener schedules.

## Fase 7 — Comandos completos

- [x] run_now.
- [x] stop_run.
- [x] pause_sync.
- [x] resume_sync.
- [x] refresh_config.
- [x] command journal.
- [x] lease expiration.
- [x] idempotencia.

Exit criteria:

- Matriz unitaria aprobada; queda la validación manual de pausa/reanudación sobre el scheduler real.

## Fase 8 — API de control + React

- [ ] Dashboard metrics.
- [ ] Agentes.
- [ ] Detalle agente.
- [ ] Runs.
- [ ] Run detail.
- [ ] Comandos.
- [ ] Auditoría.
- [ ] Clientes.
- [ ] Catálogo/asignaciones.
- [ ] Estados loading/empty/error/403.

Exit criteria:

- La maqueta usa datos reales y puede ejecutar/detener un sync.

## Fase 9 — Hardening QA

- [ ] Test de red.
- [ ] Crash tests.
- [ ] Disco lleno.
- [ ] Duplicados.
- [ ] Out-of-order.
- [ ] Cross-agent security.
- [ ] 10.000 eventos outbox.
- [ ] 24 h soak 3 agentes.

Exit criteria:

- Todos los P0 cerrados.

## Fase 10 — Piloto 3 agentes

- [ ] Instalar en 3 máquinas representativas.
- [ ] Medir duración y utilización.
- [ ] Capturar errores reales.
- [ ] Revisar intervalos.
- [ ] 7 días sin pérdida crítica.

## Fase 11 — Escala 100 agentes

- [ ] Simulador de 100 agentes.
- [ ] 24 h soak.
- [ ] Reconnection storm.
- [ ] 100 run_now simultáneos.
- [ ] 10 reinicios aleatorios durante runs.
- [ ] tuning índices/pool/timeouts.

## Dependencias críticas

```text
Contracts
   ↓
Agent Core ─────┐
   ↓            │
Outbox          │
   ↓            │
Laravel Agent API
   ↓
clientes_valery real
   ↓
Scheduler + Commands
   ↓
React real
   ↓
QA hardening
```

## Recomendación de tamaño de PR

- 1 caso de uso o frontera por PR.
- Evitar PRs > 500–800 líneas netas salvo generación/migraciones justificadas.
- Cada PR incluye tests y actualización de docs/contrato si cambia interfaz.


---

# 09 — Playbook para desarrollar con Codex

**Versión:** 1.1

## 1. Objetivo

Usar Codex como desarrollador asistido sin permitir que invente arquitectura o cambie contratos silenciosamente.

## 2. Regla de contexto

Para cada tarea, adjuntar solo:

1. documento relevante,
2. contrato JSON relevante,
3. archivos del código afectados,
4. criterios de aceptación,
5. tests esperados.

No pasar todo el paquete si la tarea es pequeña.

## 3. Plantilla de prompt para Codex

```text
Rol: actúa como desarrollador senior de [Python/Laravel/React].

Fuente de verdad:
- [archivo de especificación]
- [schema JSON]

Tarea:
[una sola tarea concreta]

Restricciones:
- No cambies contratos ni enums.
- No añadas dependencias sin justificar.
- Mantén KISS.
- No crees nuevas capas/factories/repositories salvo necesidad demostrada.
- Añade tests.
- No modifiques archivos fuera del alcance sin necesidad.

Criterios de aceptación:
1. ...
2. ...

Antes de terminar:
- ejecuta tests,
- reporta archivos cambiados,
- reporta decisiones o desviaciones,
- no declares éxito si algo falla.
```

## 4. Orden recomendado de prompts

### Prompt 001 — Scaffolding del agente

Contexto: `02_AGENTE_PYTHON.md`.

Objetivo:

- Crear paquete Python.
- Enums.
- SyncResult.
- SyncContext.
- Registry.
- Fake synchronizer.
- Tests.

No implementar HTTP todavía.

### Prompt 002 — SyncRunner

- Lock por sync_code.
- active_runs.
- worker=1.
- stop cooperativo.
- tests de carreras básicas.

### Prompt 003 — Outbox

- escritura atómica.
- pending/sending/failed.
- retry/backoff/jitter.
- recovery.

### Prompt 004 — Laravel migrations

Contexto: `05_MODELO_DE_DATOS.md`.

- migrations.
- constraints.
- factories de test solo donde aporten.
- tests de unique/cross-agent.

### Prompt 005 — Agent API heartbeat/config

### Prompt 006 — Command claim + lease

### Prompt 007 — Event ingest idempotente

### Prompt 008 — clientes_valery adapter

### Prompt 009 — LocalSyncLogRepository

### Prompt 010 — Scheduler

### Prompt 011 — stop_run end-to-end

### Prompt 012 — React Agents/Runs/Commands

## 5. Definition of Done por tarea

Una tarea está terminada cuando:

- compila/ejecuta,
- tests relevantes pasan,
- no rompe contratos,
- no introduce dependencia no aprobada,
- manejo de error está probado,
- logs no exponen secretos,
- docs se actualizan si cambió comportamiento.

## 6. Guardrails de revisión humana

Revisar manualmente:

- auth/authorization,
- transacciones de claim,
- idempotencia,
- queries e índices,
- manejo de secretos,
- cancelación y carreras,
- writes locales a sync_success/sync_errors,
- outbox y recuperación.

No aceptar automáticamente código generado en estas áreas.

## 7. Práctica de ramas

Sugerencia:

```text
main
feature/agent-core
feature/outbox
feature/agent-api-heartbeat
feature/command-claim
feature/clientes-valery
```

PRs pequeñas y revisión por dominio.

## 8. Commit messages sugeridos

```text
feat(agent): add cooperative sync runner
feat(api): implement command claim lease
fix(outbox): recover stale sending events
feat(sync): adapt clientes_valery to SyncResult
feat(ui): show stopping and interrupted run states
test(scale): simulate 100 polling agents
```

## 9. Qué no pedir a Codex en una sola tarea

No usar prompts como:

```text
"Construye todo BAPPS Sync completo"
```

Eso aumenta incoherencias. Dividir por vertical slice y contrato.

## 10. Primera secuencia práctica de 5 PRs

1. `agent-core-contracts`
2. `agent-sync-runner-stop`
3. `agent-outbox-durable`
4. `center-agent-heartbeat-config`
5. `center-command-claim-event-ingest`

Después integrar `clientes_valery`.


---

# 10 — ADR: registro de decisiones de arquitectura

**Versión:** 1.1

## ADR-001 — Laravel monolítico modular

**Decisión:** una sola app Laravel con dominios internos.  
**Motivo:** simplicidad operativa y suficiente escala para MVP/100 agentes.  
**Revisar si:** aparecen límites de despliegue independientes demostrados.

## ADR-002 — React + TypeScript + Vite reemplaza Blade + Livewire

**Decisión:** el frontend definitivo será SPA React.  
**Motivo:** la interfaz ya diseñada es rica en drawers, filtros, polling, estados remotos y mutaciones.  
**Impacto:** la especificación v1.0 que decía Blade/Livewire queda superseded.

## ADR-003 — Polling en lugar de push entrante

**Decisión:** agente inicia HTTPS; command polling 5 s + jitter.  
**Motivo:** seguridad, NAT/firewalls, KISS.  
**Revisar si:** sub-segundo es requisito real o carga medida lo exige.

## ADR-004 — Scheduler local, configuración central

**Decisión:** Laravel define intervalos; agente ejecuta localmente.  
**Motivo:** autonomía offline.  
**Política:** UTC, slots fijos, coalescing de missed schedules.

## ADR-005 — stop_run es comando MVP

**Decisión:** añadir `stop_run`.  
**Motivo:** requisito real de control.  
**Implementación:** cancelación cooperativa y estado `stopping`.

## ADR-006 — pause_sync no detiene ejecución activa

**Decisión:** pausa futuras ejecuciones.  
**Motivo:** semántica clara; para detener se usa `stop_run`.

## ADR-007 — Un worker por agente inicialmente

**Decisión:** `max_workers=1`.  
**Motivo:** reducir carga y carreras hasta tener métricas.  
**Revisar si:** utilización p95 sostenida > 0,70 o backlog operacional.

## ADR-008 — Outbox JSON como garantía central

**Decisión:** archivos JSON, un evento por archivo, escritura atómica.  
**Motivo:** no instalar DB adicional.  
**Importante:** la BD BAPPS existente del cliente no cuenta como DB interna del agente.

## ADR-009 — sync_success/sync_errors son logs operacionales locales

**Decisión:** el agente escribe ambas tablas a través de un repositorio centralizado.  
**Fuente de verdad central:** evento/outbox + sync_runs.  
**Motivo:** la BD local puede estar caída precisamente cuando ocurre un error.

## ADR-010 — Centro no recibe toda la data de negocio en MVP

**Decisión:** fuera de alcance `POST /agent/sync/{sync_code}/batches` para datos administrativos completos.  
**Motivo:** el caso actual necesita control y telemetría; evitar alcance innecesario.

## ADR-011 — Claim de comandos con POST, lease e idempotencia

**Decisión:** `POST /agent/commands/claim`.  
**Motivo:** expresa efecto lateral y permite claim transaccional.  
**Recuperación:** lease vencida + command journal local.

## ADR-012 — Coalescing de schedules perdidos

**Decisión:** máximo una ejecución catch-up por sync_code.  
**Motivo:** evitar tormenta de backlog después de reinicio/offline.

## ADR-013 — Jitter obligatorio

**Decisión:** polling, heartbeat y retries tienen jitter.  
**Motivo:** evitar thundering herd y reconnect storms a 100 agentes.

## ADR-014 — agent_syncs como nombre de asignación

**Decisión:** usar `agent_syncs` en lugar de `client_syncs` en el nuevo plan.  
**Motivo:** la ejecución, configuración y scheduler pertenecen a un agente concreto; el cliente se deriva por relación.

## ADR-015 — Máquinas de estado cerradas

**Decisión:** enums compartidos y transiciones explícitas.  
**Motivo:** equipo, idempotencia, eventos fuera de orden y UI consistente.


---

# 11 — Checklist de aceptación del MVP

**Versión:** 1.1

## A. Arquitectura y contratos

- [ ] Documentos v1.1 aceptados por el equipo.
- [ ] JSON Schemas versionados en repositorio.
- [ ] Enums idénticos en Python, Laravel y TypeScript.
- [ ] No hay endpoint o campo crítico sin contrato.

## B. Agente

- [ ] Servicio Windows inicia automáticamente.
- [ ] Single-instance lock.
- [ ] Enrolamiento individual.
- [ ] Heartbeat con jitter.
- [ ] Config cache válida.
- [ ] Scheduler UTC.
- [ ] Coalescing.
- [ ] Worker no bloquea control loop.
- [ ] SyncRunner único.
- [ ] Lock por sync_code.
- [ ] stop cooperativo.
- [ ] command journal.
- [ ] outbox durable.
- [ ] recuperación crash.
- [ ] logs estructurados sin secretos.

## C. Comandos

- [ ] run_now.
- [ ] stop_run.
- [ ] pause_sync.
- [ ] resume_sync.
- [ ] refresh_config.
- [ ] claim transaccional.
- [ ] lease.
- [ ] expiración.
- [ ] idempotencia.
- [ ] cross-agent protegido.

## D. Sincronizador clientes_valery

- [ ] Implementa contrato.
- [ ] Inyección de conectores.
- [ ] SyncResult.
- [ ] Métricas.
- [ ] Puntos seguros de stop.
- [ ] Idempotencia documentada.
- [ ] Error handling clasificado.

## E. Logs locales

- [x] Success escribe sync_success.
- [x] Failed escribe sync_errors.
- [x] Interruption no se disfraza como error técnico por defecto.
- [x] BD caída no oculta el error central.

## F. Centro Laravel

- [ ] Migraciones/constraints.
- [ ] Heartbeat.
- [ ] Config.
- [ ] Command claim/result.
- [ ] Event ingest idempotente.
- [ ] Out-of-order safe.
- [ ] Audit.
- [ ] APIs de control.

## G. React

- [ ] Dashboard real.
- [ ] Lista/detalle agentes.
- [ ] Runs.
- [ ] run_now.
- [ ] stop_run.
- [ ] pause/resume.
- [ ] loading/empty/error/403.
- [ ] estados running/stopping/interrupted.

## H. QA P0

- [ ] Duplicado evento.
- [ ] Duplicado comando.
- [ ] Lease vencida.
- [ ] Reinicio running.
- [ ] Reinicio outbox.
- [ ] Disco lleno.
- [ ] API caída.
- [ ] Reconnection storm.
- [ ] Scheduler + run_now race.
- [ ] stop + finish race.
- [ ] doble instancia.
- [ ] cross-agent.
- [ ] config corrupta.

## I. Piloto 3 agentes

- [ ] 7 días.
- [ ] 0 pérdida crítica.
- [ ] 0 duplicado funcional.
- [ ] utilización medida.
- [ ] intervalos ajustados con datos.

## J. 100 agentes

- [ ] simulador.
- [ ] 24 h soak.
- [ ] p95/p99 medidos.
- [ ] reconnect storm.
- [ ] 100 run_now simultáneos.
- [ ] 10 reinicios aleatorios.
- [ ] índices revisados con EXPLAIN/queries reales.

## Gate final

El MVP no entra en producción ampliada mientras exista un P0 abierto.


---

# Revisión de coherencia v1.1 — dos pasadas

## Pasada 1 — Arquitectura y alcance

Se revisaron las decisiones históricas contra la propuesta actual y se resolvieron estas contradicciones:

1. Frontend: Blade + Livewire queda sustituido por React + TypeScript + Vite.
2. Comandos: `stop_run` se incorpora al MVP y se diferencia de `pause_sync`.
3. Persistencia local: "sin MySQL local" significa no instalar una DB propia del agente; la BD BAPPS existente del cliente sí es usada para datos y logs.
4. Data central: el MVP no requiere enviar todos los datos administrativos al centro; el centro recibe control y telemetría.
5. Asignaciones: se normaliza el concepto como `agent_syncs`.
6. Config status: se evita duplicar `enabled BOOLEAN` y `status`.
7. Comandos: claim explícito con lease e idempotencia.
8. Scheduler: slots fijos UTC + coalescing.
9. Concurrencia: un worker inicial; no dos recomendaciones contradictorias.
10. Logs: `sync_success`/`sync_errors` son operación local, no garantía central única.

Resultado: arquitectura coherente.

## Pasada 2 — QA, carreras y escalabilidad

Se revisaron fallos P0 y escala a 100 agentes:

- thundering herd → jitter.
- reconnect storm → backoff+jitter+flush limitado.
- respuesta perdida → idempotencia event_id/command journal.
- claimed eterno → lease.
- run huérfano → reconciliación startup.
- scheduler backlog → coalescing.
- stop durante driver bloqueante → stopping + cancelación cooperativa.
- outbox no escribible → fail-safe antes de nuevas ejecuciones críticas.
- local DB caída → outbox/log central independiente.
- eventos fuera de orden → proyección monotónica de estados.
- 100 agentes → ~23,3 req/s promedio de control; índices y soak obligatorios.

Resultado: no se identificó una necesidad de cambiar polling, monolito modular o outbox para el objetivo de 100 agentes.

## Decisiones abiertas no bloqueantes

Estas pueden resolverse durante implementación sin reabrir arquitectura:

- Driver HTTP concreto en Python (`requests` vs `httpx`).
- Librería exacta del servicio Windows.
- Formato final de ULID/UUID prefijados.
- Duración exacta de command lease (recomendación inicial: 120 s).
- Retención exacta de eventos centrales.
- Tamaño de lotes de flush de outbox.

Deben convertirse en configuración o ADR cuando se decidan.
