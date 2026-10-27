# 03 — Centro Laravel, API y frontend

**Versión:** 1.1

## 1. Arquitectura del centro

Laravel será un monolito modular. Una sola aplicación desplegable, con límites internos claros.

```text
app/
├── Domains/
│   ├── Clients/
│   ├── Agents/
│   ├── SyncCatalog/
│   ├── AgentSyncs/
│   ├── Commands/
│   ├── Runs/
│   ├── Events/
│   ├── Audit/
│   └── Security/
├── Http/
│   ├── Controllers/
│   │   ├── AgentApi/
│   │   └── ControlApi/
│   ├── Requests/
│   ├── Resources/
│   └── Middleware/
└── Jobs/
```

No se usará repository pattern en todos los modelos por defecto. Los controllers deben ser delgados; los casos de uso viven en Actions/Services.

## 2. Dos superficies de API

### 2.1 API del agente

Autenticación máquina-a-máquina por credencial individual.

### Enrolamiento y credencial

Un agente debe existir previamente en el centro, con una credencial de enrolamiento de un solo uso almacenada únicamente como hash. `POST /agent/enroll` recibe `agent_code`, `enrollment_token`, `machine_name`, `agent_version` y `os` opcional. Si el token es válido, el centro rota la credencial y devuelve una sola vez `agent_token` junto con el código y la versión de configuración.

Las llamadas posteriores llevan `Authorization: Bearer <agent_token>` y el header `X-Agent-Code`. El middleware verifica ambos contra el agente activo; cualquier `agent_code` presente en heartbeat, claim o evento debe coincidir con el autenticado. Así se evita confiar en un código enviado solo en el payload y se protege contra cross-agent access.

```text
POST /api/v1/agent/enroll
POST /api/v1/agent/heartbeat
GET  /api/v1/agent/config
POST /api/v1/agent/commands/claim
POST /api/v1/agent/commands/{command_id}/result
POST /api/v1/agent/events
```

### 2.2 API del centro de control

```text
POST   /api/v1/auth/login
GET    /api/v1/dashboard/metrics
GET    /api/v1/agents
GET    /api/v1/agents/{code}
POST   /api/v1/agents/{code}/commands
PATCH  /api/v1/agents/{code}/syncs/{sync_code}
GET    /api/v1/runs
GET    /api/v1/runs/{run_id}
POST   /api/v1/runs/{run_id}/retry
GET    /api/v1/audit
GET    /api/v1/clients
GET    /api/v1/clients/{id}
GET    /api/v1/syncs
POST   /api/v1/syncs
PATCH  /api/v1/syncs/{code}
```

El contrato HTTP público de estas rutas — DTOs, envolturas, errores, mapeos de API Resource y límites de los drawers — está congelado en `12_CONTRATO_API_CONTROL_v1.md`. Los tipos y handlers MSW del frontend son su especificación ejecutable.

## 3. Claim de comandos

No se recomienda un `GET` con efecto lateral. El agente reclama comandos con:

```text
POST /api/v1/agent/commands/claim
```

Request:

```json
{
  "agent_code": "AGT-000142",
  "max_commands": 5,
  "known_command_ids": ["CMD-5001"]
}
```

Response:

```json
{
  "data": [
    {
      "schema_version": "1.0",
      "command_id": "CMD-5002",
      "type": "run_now",
      "issued_at": "2026-07-15T18:00:00Z",
      "expires_at": "2026-07-15T18:10:00Z",
      "lease_expires_at": "2026-07-15T18:02:00Z",
      "idempotency_key": "idem-...",
      "payload": {
        "sync_code": "clientes_valery"
      }
    }
  ]
}
```

Reglas transaccionales del claim:

- Solo comandos `pending` y no expirados.
- Solo del agente autenticado.
- Cambiar a `claimed` en la misma transacción.
- Registrar `claimed_at` y `lease_expires_at`.
- Limitar cantidad.
- Ordenar por `created_at ASC`.
- Índice compuesto por patrón de consulta.

Si vence lease sin resultado, el comando puede volver a `pending`, pero el agente debe protegerse con el journal local para no repetir un comando ya completado.

## 4. Resultado de comando

```text
POST /api/v1/agent/commands/{command_id}/result
```

Ejemplo:

```json
{
  "status": "completed",
  "completed_at": "2026-07-15T18:00:14Z",
  "result": {
    "run_id": "RUN-20260715-000142"
  }
}
```

Validaciones:

- command pertenece al agente autenticado.
- transición válida.
- idempotencia: repetir el mismo resultado no produce efectos adicionales.

## 5. Heartbeat

Request:

```json
{
  "schema_version": "1.0",
  "agent_code": "AGT-000142",
  "agent_version": "1.0.0",
  "config_version": 18,
  "machine_name": "SERVER-VALERY",
  "status": "online",
  "running_runs": [
    {
      "run_id": "RUN-20260715-000142",
      "sync_code": "clientes_valery",
      "status": "running",
      "started_at": "2026-07-15T17:55:00Z"
    }
  ],
  "outbox": {
    "pending_count": 3,
    "pending_bytes": 8120
  }
}
```

Response:

```json
{
  "acknowledged": true,
  "latest_config_version": 19,
  "has_pending_commands": true,
  "server_time": "2026-07-15T18:00:00Z"
}
```

## 6. Configuración

El centro es fuente de verdad. El agente conserva la última versión válida.

```json
{
  "schema_version": "1.0",
  "version": 19,
  "agent_code": "AGT-000142",
  "syncs": [
    {
      "code": "clientes_valery",
      "status": "enabled",
      "interval_seconds": 900,
      "config": {}
    },
    {
      "code": "ventas_valery",
      "status": "paused",
      "interval_seconds": 14400,
      "config": {}
    }
  ]
}
```

No enviar secretos innecesarios. Los secretos locales deben resolverse por mecanismo seguro de instalación/config local cuando sea posible.

## 7. Ingesta de eventos

```text
POST /api/v1/agent/events
```

Reglas P0:

- `event_id` único.
- Validar `agent_code` contra autenticación.
- Repetir evento ya procesado devuelve ACK lógico exitoso.
- Soportar eventos fuera de orden.
- `run_finished` puede llegar antes de `run_started`; la proyección no debe retroceder un estado terminal a `running`.
- Persistir evento bruto y luego proyectar.

## 8. Frontend definitivo

```text
React
TypeScript
Vite
React Router
TanStack Query
```

Estructura:

```text
src/
├── app/
├── api/
├── features/
│   ├── dashboard/
│   ├── agents/
│   ├── runs/
│   ├── commands/
│   ├── audit/
│   ├── clients/
│   └── syncs/
├── components/
│   ├── ui/
│   └── layout/
└── lib/
    ├── statuses.ts
    ├── errors.ts
    ├── dates.ts
    └── formatters.ts
```

No Redux inicialmente. TanStack Query maneja estado remoto; estado local se limita a drawers, filtros, tabs y modales.

## 9. Polling en frontend

Sugerencia inicial:

| Dato | Frecuencia |
|---|---:|
| Dashboard | 15 s |
| Runs visibles `running/stopping` | 5–10 s |
| Estado de comando recién emitido | 5 s hasta terminal |
| Lista de agentes | manual + 30 s si la operación lo requiere |

Esto es polling de UI y es independiente del polling del agente.

## 10. Seguridad y tenancy

- Cada agente solo ve su configuración y comandos.
- Cada evento se vincula al agente autenticado, no se confía ciegamente en `agent_code` del payload.
- RBAC para usuarios.
- Auditoría de comandos y cambios de config.
- Rate limiting primario por credencial/agent_id; protección secundaria por IP.
- HTTPS obligatorio.
- No registrar secretos completos.

## 11. Manejo de 100 agentes

Con 100 agentes, polling cada 5 s y heartbeat cada 30 s producen aproximadamente 23,3 req/s promedio en steady state. No justifica microservicios. Sí exige:

- índices correctos,
- jitter,
- timeouts,
- pool de conexiones bien dimensionado,
- pruebas de carga,
- evitar N+1,
- respuestas pequeñas,
- paginación,
- retención de eventos.
