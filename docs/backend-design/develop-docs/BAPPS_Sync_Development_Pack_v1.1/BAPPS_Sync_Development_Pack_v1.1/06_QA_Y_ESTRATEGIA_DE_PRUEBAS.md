# 06 — Estrategia QA del MVP

**Versión:** 1.1  
**Rol:** Gate de calidad antes de piloto y antes de 100 agentes.

## 1. Política de severidad

### P0 — Bloqueante

Puede causar pérdida silenciosa, duplicado funcional, ejecución incorrecta, acceso cross-tenant, corrupción o incapacidad de recuperación.

### P1 — Alta

Degrada operación, observabilidad o confiabilidad, pero existe recuperación manual razonable.

### P2 — Media

Problema de UX, diagnóstico o eficiencia sin riesgo inmediato de datos.

## 2. P0 obligatorios

1. `event_id` duplicado no duplica efectos.
2. Comando duplicado no crea una segunda ejecución.
3. Comando claimed con agente caído se recupera mediante lease.
4. Reinicio durante ejecución no deja run eternamente `running`.
5. Reinicio durante escritura outbox no pierde ni corrompe silenciosamente el evento.
6. Scheduler + run_now simultáneos no ejecutan dos veces el mismo sync.
7. stop_run + finalización simultánea produce un único estado terminal coherente.
8. Agente incorrecto no puede reclamar comando ajeno.
9. Evento de otro agente/cliente se rechaza.
10. API caída no detiene schedules locales autorizados.
11. Reconexión no crea tormenta sincronizada sin backoff/jitter.
12. Disco lleno/outbox no disponible se detecta y bloquea nuevas ejecuciones críticas según política.
13. BD BAPPS caída no elimina la capacidad de reportar el error central mediante outbox/log.
14. Dos instancias del agente no pueden operar simultáneamente.
15. Config corrupta no reemplaza última configuración válida.

## 3. Matriz funcional mínima

| Área | Casos obligatorios |
|---|---|
| Instalación | limpia, reinstalación, servicio auto-start, permisos, doble instancia |
| Enrolamiento | token válido, inválido, usado, expirado, agente disabled |
| Heartbeat | OK, timeout, 401, 403, 429, 500, reloj desviado, payload inválido |
| Config | primera, sin cambio, nueva versión, JSON inválido, sync desconocido, intervalo inválido |
| Scheduler | 15 min, 4 h, coincidencias, pausa, reinicio, missed schedules, DST/UTC |
| run_now | normal, duplicado, expirado, inexistente, no autorizado, paused, ya running |
| stop_run | normal, duplicado, terminado, inexistente, otro agente, durante query y batch |
| pause/resume | idempotencia, ejecución activa, no backlog retroactivo |
| SyncRunner | success, error origen, error destino, excepción inesperada, lock, métricas |
| sync_success | insert OK, DB caída, timeout, caracteres especiales, commit con respuesta perdida |
| sync_errors | mismos casos + error que impide escribir en la propia tabla |
| Outbox | ACK, retry, pérdida de respuesta, corrupto, disco lleno, permisos, crash |
| Eventos | duplicado, fuera de orden, payload inválido, run inexistente, cross-agent |
| Reinicios | idle, running, stopping, outbox write, HTTP send, config update |
| Red | DNS, connect timeout, read timeout, TLS, intermitencia, 429, 5xx |
| Seguridad | token robado, replay, comando expirado, payload gigante, secretos en logs |
| Frontend | loading, empty, error, retry, pending, expired, failed, stopping, offline |

## 4. Tests unitarios del agente

- `SyncContext.raise_if_stopped`.
- Transiciones de run.
- Transiciones de comando.
- Scheduler de slots fijos.
- Coalescing de missed schedules.
- Lock por sync_code.
- Single-instance lock.
- Backoff + jitter.
- Serialización de eventos.
- Escritura atómica outbox.
- Recuperación de `sending/`.
- JSON corrupto.
- Command journal idempotente.
- ErrorClassifier.
- Validación config.

## 5. Tests de integración del agente

- Firebird real/controlado disponible y caído.
- SQL Server cuando se incorpore Profit.
- BD BAPPS disponible y caída.
- Laravel disponible y caída.
- Respuesta HTTP perdida después del commit.
- Reinicio del proceso durante diferentes etapas.
- `stop_run` con sincronizador real que procesa por lotes.

## 6. Tests Laravel

- Claim transaccional de comandos.
- Dos claims concurrentes no entregan mismo comando dos veces sin control de lease.
- Expiración.
- Resultado duplicado.
- Event idempotency.
- Out-of-order projection.
- Cross-agent authorization.
- Constraints/unique keys.
- Paginación y filtros.
- Dashboard sin N+1.

## 7. Tests E2E

### E2E-01 éxito

```text
React → run_now → Laravel → claim → agente → clientes_valery
→ sync_success → outbox → Laravel → sync_runs → React
```

### E2E-02 error de origen

```text
Firebird caído → sync_errors + evento failed → UI muestra error operativo
```

### E2E-03 central offline

```text
Laravel offline → sync local continúa → outbox crece → Laravel vuelve → entrega eventual
```

### E2E-04 stop

```text
run larga → stop_run → stopping → punto seguro → interrupted
```

### E2E-05 duplicado

```text
servidor hace commit de EVT-123 → respuesta se pierde → reenvío EVT-123 → un solo efecto
```

## 8. Pruebas de carrera obligatorias

- Scheduler y run_now para el mismo sync en el mismo segundo.
- Dos run_now simultáneos.
- stop_run y success simultáneos.
- pause_sync y slot scheduler simultáneos.
- Cambio config mientras scheduler evalúa.
- Reinicio después de claim y antes de iniciar run.
- Reinicio después de finalizar y antes de reportar comando completed.

## 9. Pruebas de resiliencia

- Centro 30 min offline.
- Centro 24 h offline en un agente.
- 10.000 eventos pendientes.
- Outbox de 1 GB en entorno de prueba.
- Un archivo corrupto entre miles válidos.
- DNS intermitente.
- 429 sostenido.
- 500 alternante.
- 10 agentes reiniciándose aleatoriamente durante runs.

## 10. Criterios de aprobación del piloto de 3 agentes

- 7 días de operación sin pérdida crítica.
- 0 duplicados funcionales.
- 0 cross-tenant.
- 0 runs huérfanos indefinidos.
- 100% de comandos terminales con auditoría.
- Outbox recuperada tras caídas simuladas.
- stop_run probado en sync real.
- utilización del worker medida por agente.

## 11. Criterios de aprobación para 100 agentes

- 24 h de soak mínimo.
- 100 agentes simulados o reales.
- polling y heartbeat con jitter.
- p95 API control < 300 ms como objetivo inicial.
- p99 < 1 s como objetivo inicial.
- 5xx < 0,1% bajo carga objetivo.
- 0 eventos críticos perdidos.
- 0 duplicados funcionales.
- 99% de `run_now` recibido por agente online en < 10 s.
- reconnection storm absorbida sin caída prolongada.

Estos valores son objetivos de prueba, no garantías sin medición.
