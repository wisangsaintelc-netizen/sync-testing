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

- [ ] Success escribe sync_success.
- [ ] Failed escribe sync_errors.
- [ ] Interruption no se disfraza como error técnico por defecto.
- [ ] BD caída no oculta el error central.

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
