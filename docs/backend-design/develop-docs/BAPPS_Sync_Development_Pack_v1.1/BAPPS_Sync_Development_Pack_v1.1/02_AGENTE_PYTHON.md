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
