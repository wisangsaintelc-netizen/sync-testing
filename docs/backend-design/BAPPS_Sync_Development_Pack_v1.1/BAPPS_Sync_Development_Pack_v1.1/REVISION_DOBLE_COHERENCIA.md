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
