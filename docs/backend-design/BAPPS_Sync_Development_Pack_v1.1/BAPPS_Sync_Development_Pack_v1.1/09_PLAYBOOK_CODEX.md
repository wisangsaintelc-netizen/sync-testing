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
