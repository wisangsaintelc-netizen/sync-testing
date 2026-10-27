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
name
source_type
min_agent_version
enabled_globally
default_interval_seconds
description
created_at
updated_at
```

`default_interval_seconds` es obligatorio, entero y `>= 60`. Es el valor inicial sugerido al crear una asignación; no controla directamente ningún scheduler ya asignado. La API de control lo expone como `interval_seconds` por compatibilidad con la SPA; el mapeo se centraliza en un API Resource.

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

`agent_syncs.interval_seconds` es el intervalo efectivo del scheduler. Cambiarlo no altera `sync_catalog.default_interval_seconds` ni otras asignaciones.

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
