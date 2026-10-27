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
