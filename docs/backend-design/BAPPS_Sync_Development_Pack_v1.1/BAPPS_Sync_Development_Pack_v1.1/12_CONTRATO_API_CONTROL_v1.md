# 12 — Contrato de la API de control v1

**Estado:** congelado para la primera implementación Laravel.  
**Fecha:** 17 de julio de 2026.  
**Ámbito:** API consumida por la SPA React; no sustituye los contratos agente↔centro de `04_CONTRATOS_Y_MAQUINAS_DE_ESTADO.md` ni los JSON Schema de `contracts/`.

## 1. Fuente de verdad y regla de compatibilidad

La especificación ejecutable actual es:

- `resources/js/api/types.ts` — nombres y tipos públicos.
- `resources/js/api/endpoints.ts` — métodos, rutas y payloads.
- `resources/js/mocks/handlers.ts` — comportamiento HTTP de referencia.

Laravel debe implementar este contrato sin modificar las vistas React. Si se requiere cambiarlo, se actualizan en el mismo cambio los tipos, los handlers MSW, este documento y las pruebas de contrato.

El modelo Eloquent es interno. Los controladores devuelven API Resources con los nombres públicos definidos aquí; nunca se filtran nombres de columnas por accidente.

## 2. Convenciones HTTP

- Prefijo: `/api/v1`.
- Fechas: ISO 8601 UTC; una fecha ausente es `null`.
- Colecciones: `{ data, page, page_size, total }`.
- Recursos individuales y mutaciones: JSON directo del recurso, sin envoltura `data`.
- Error: `{ "error": { "code": "CODIGO", "message": "mensaje" } }`.
- Paginación por defecto: `page=1`, `page_size=25`; `page_size` máximo 100.
- Filtros comunes: `status`, `search`, `page`, `page_size`. Cada endpoint ignora los filtros que no le correspondan.
- Los comandos de control usan el payload plano de este documento. El comando que Laravel entrega al agente conserva el sobre versionado `{ schema_version, command_id, payload, ... }` de `contracts/command.v1.schema.json`.

## 3. Autenticación de control

`POST /auth/login` recibe:

```json
{ "email": "operaciones@bapps", "password": "..." }
```

Responde:

```json
{
  "token": "...",
  "user": { "name": "Operaciones", "email": "operaciones@bapps", "role": "operator" }
}
```

La V1 usa token Sanctum con `Authorization: Bearer <token>`, igual que la SPA actual. Debe limitarse por habilidad/rol, expirar o poder revocarse y nunca escribirse en logs. Cualquier migración futura a sesión cookie HttpOnly exige una ADR y el ajuste coordinado del cliente HTTP.

## 4. Endpoints

| Método y ruta | Request | Respuesta |
|---|---|---|
| `POST /auth/login` | credenciales | `LoginResponse` |
| `GET /dashboard/metrics` | — | `DashboardMetrics` |
| `GET /agents` | filtros de colección | `ListResponse<AgentListItem>` |
| `GET /agents/{code}` | — | `AgentDetail` |
| `POST /agents/{code}/commands` | `{ type, sync_code?, run_id? }` | `Command` |
| `PATCH /agents/{code}/syncs/{sync_code}` | `{ status?, interval_seconds? }` | `AgentDetail` |
| `GET /runs` | filtros de colección | `ListResponse<RunListItem>` |
| `GET /runs/{id}` | — | `RunDetail` |
| `POST /runs/{id}/retry` | — | `RunListItem` nuevo |
| `GET /audit` | filtros de colección | `ListResponse<AuditEvent>` |
| `GET /clients` | filtros de colección | `ListResponse<ClientListItem>` |
| `GET /clients/{id}` | — | `ClientDetail` |
| `GET /syncs` | filtros de colección | `ListResponse<SyncCatalogItem>` |
| `POST /syncs` | catálogo, sin `enabled` obligatorio | `SyncCatalogItem` |
| `PATCH /syncs/{code}` | campos editables del catálogo | `SyncCatalogItem` |

Validaciones P0: códigos de sync únicos e inmutables; `interval_seconds >= 60`; `type` debe ser un `CommandType`; `stop_run` exige `run_id`; `run_now`, `pause_sync` y `resume_sync` exigen `sync_code`; cada recurso solicitado debe pertenecer al ámbito autorizado del usuario.

## 5. Recursos públicos

Los campos completos están tipados en `resources/js/api/types.ts`. Los mapeos que deben mantenerse explícitos son:

| Modelo interno | API React |
|---|---|
| `agents.agent_code` | `Agent*.code` |
| `agents.machine_name`, `last_seen_at`, `last_ip` | `machine`, `last_heartbeat`, `ip` |
| `sync_runs.run_id`, `finished_at`, `error_code` | `Run*.id`, `ended_at`, `error` |
| `sync_catalog.source_type`, `description`, `enabled_globally` | `SyncCatalogItem.source`, `desc`, `enabled` |
| `sync_catalog.default_interval_seconds` | `SyncCatalogItem.interval_seconds` |
| `sync_catalog.functional_key` | `SyncCatalogItem.key` |

`RunDetail` agrega `correlation_id`, `timeline` y, para diagnósticos autorizados, `tech_message`. El campo `error` contiene el código operativo; el mensaje técnico no sustituye a `lib/errors.ts` para la UI.

`AgentDetail` y `ClientDetail` incluyen colecciones recientes para el drawer. En V1 se devuelven como máximo 20 `commands`, 20 `runs` y 50 elementos de `timeline`, ordenados del más reciente al más antiguo. Si un caso de uso requiere histórico completo, debe usar los endpoints paginados de runs o auditoría, no agrandar estos drawers sin límite.

## 6. Catálogo y asignación

El catálogo global define qué sincronizador existe y una **frecuencia predeterminada** (`default_interval_seconds` en persistencia; `interval_seconds` en la API pública). Se utiliza al crear una asignación nueva.

`agent_syncs.interval_seconds` es la frecuencia efectiva y fuente de verdad del scheduler para ese agente. `PATCH /agents/{code}/syncs/{sync_code}` la puede cambiar sin alterar el valor predeterminado del catálogo ni las demás asignaciones.

El catálogo puede deshabilitarse globalmente; la asignación mantiene su `status` independiente (`enabled`, `paused`, `disabled`). No se añade un booleano `enabled` a `agent_syncs`.

## 7. Implementación Laravel

- Controllers delgados en `Http/Controllers/ControlApi`; validación mediante Form Requests.
- Acciones/servicios por caso de uso; transacciones para emitir comandos, reintentar ejecuciones y cambiar asignaciones.
- API Resources para todas las respuestas públicas y eager loading selectivo para evitar N+1.
- Policies o middleware de ámbito antes de buscar o mutar recursos.
- Pruebas de contrato que comparen cada respuesta real con los casos de los handlers MSW, incluyendo 401, 403, 404 y 422.
