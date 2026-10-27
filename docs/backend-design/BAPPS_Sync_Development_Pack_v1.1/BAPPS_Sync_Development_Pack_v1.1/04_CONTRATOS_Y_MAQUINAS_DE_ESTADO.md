# 04 — Contratos, enums y máquinas de estado

**Versión:** 1.1

## 1. Regla

Los contratos versionados son la interfaz entre Python, Laravel y React. Los JSON Schema de referencia están en `contracts/`.

Los JSON Schema de este directorio gobiernan el protocolo agente↔centro. La API de control React↔Laravel se especifica por separado en `12_CONTRATO_API_CONTROL_v1.md`, para no mezclar sus DTOs de presentación con los mensajes durables del agente.

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
