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
