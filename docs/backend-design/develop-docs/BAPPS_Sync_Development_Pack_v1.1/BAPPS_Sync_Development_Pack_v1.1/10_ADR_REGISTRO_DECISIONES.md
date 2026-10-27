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

## ADR-016 — Contrato de control derivado de la SPA

**Decisión:** `12_CONTRATO_API_CONTROL_v1.md`, `resources/js/api/types.ts`, `resources/js/api/endpoints.ts` y los handlers MSW definen conjuntamente la API React↔Laravel v1.  
**Motivo:** el frontend funcional ya es una especificación ejecutable; Laravel debe reemplazar los mocks sin modificar vistas.  
**Implementación:** controllers delgados, Form Requests, Actions/Services y API Resources traducen el modelo interno a esos DTOs públicos.  
**Consecuencia:** cualquier cambio de contrato exige actualizar las cuatro fuentes y sus pruebas de contrato.

## ADR-017 — Intervalo predeterminado de catálogo y efectivo por agente

**Decisión:** `sync_catalog.default_interval_seconds` conserva la frecuencia predeterminada que la SPA muestra como `interval_seconds`; `agent_syncs.interval_seconds` es el intervalo efectivo del scheduler.  
**Motivo:** concilia el alta de catálogo ya implementada con que el scheduler pertenece a un agente.  
**Consecuencia:** cambiar un catálogo no reprograma agentes existentes; cambiar una asignación solo afecta a ese agente.
