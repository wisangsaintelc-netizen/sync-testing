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
- [ ] Aprobar `12_CONTRATO_API_CONTROL_v1.md` y mantener `resources/js/api/` + MSW como especificación ejecutable de la API React↔Laravel.
- [ ] Crear CI básico.

Exit criteria:

- Los JSON Schema validan ejemplos correctos y rechazan ejemplos inválidos.
- No quedan enums contradictorios.
- Cada endpoint de control tiene request, response, error y mapeo de Resource definidos.

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

- [ ] `LocalSyncLogRepository`.
- [ ] éxito → sync_success.
- [ ] fallo → sync_errors.
- [ ] fallback si DB local no disponible.
- [ ] tests de commit/timeout/error.

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

- [ ] run_now.
- [ ] stop_run.
- [ ] pause_sync.
- [ ] resume_sync.
- [ ] refresh_config.
- [ ] command journal.
- [ ] lease expiration.
- [ ] idempotencia.

Exit criteria:

- Matriz de carreras P0 aprobada.

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
