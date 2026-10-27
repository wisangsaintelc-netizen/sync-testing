# BAPPS Sync — Plan de implementación del Frontend v1.0

**Fecha:** 17 de julio de 2026
**Alcance:** solo frontend funcional (React + TypeScript + Vite) montado sobre un proyecto Laravel (última versión). El backend real se implementa después; el front opera contra una **capa de API simulada (mocks)** que implementa exactamente el contrato de la Guía Técnica, de modo que al conectar Laravel no haya que tocar las vistas.

**Fuentes de verdad (no reinterpretar):**

> **Actualización posterior a F6 (17 de julio de 2026):** para la conexión con Laravel, el contrato de control se consolidó en `backend-design/develop-docs/BAPPS_Sync_Development_Pack_v1.1/BAPPS_Sync_Development_Pack_v1.1/12_CONTRATO_API_CONTROL_v1.md`. Este plan conserva el alcance y la implementación del frontend; aquel documento gobierna la frontera HTTP React↔Laravel.

| Documento | Qué gobierna |
|---|---|
| `docs/frontend-design/BAPPS Sync - Documentacion.dc.html` | Sistema visual: paleta, tipografía, componentes, sistema de estados, arquitectura de vistas |
| `docs/frontend-design/BAPPS Sync - Guia Tecnica.dc.html` | Contrato de API: endpoints, payloads, enums, envoltura de listados, errores, estructura de código |
| `docs/frontend-design/BAPPS Sync (standalone).html` | Maqueta navegable de referencia (píxel y comportamiento) |
| `docs/BAPPS_SYNC_PLAN_MAESTRO_v1.1.md` | Arquitectura global, enums compartidos, fases del sistema completo |

> La maqueta se puede ver localmente sirviendo `docs/frontend-design/` por HTTP (ej. `python -m http.server 8123`) y abriendo `BAPPS Sync (standalone).html`. No funciona por `file://`.

---

## 1. Decisiones de arquitectura del frontend

| Tema | Decisión | Motivo |
|---|---|---|
| Proyecto | **Un solo proyecto Laravel** creado ahora (`composer create-project laravel/laravel bapps-sync-center`), con la SPA React en `resources/js/` vía `laravel-vite-plugin` | Forma final de despliegue desde el día 1; no hay migración posterior de un Vite standalone a Laravel. Herd ya está instalado en la máquina de desarrollo |
| Versión Laravel | La última estable al momento del scaffold (objetivo: Laravel 13) | `composer create-project` trae la última; verificar en el arranque |
| SPA | React 19 + TypeScript estricto + Vite | Decisión del plan maestro (ADR-002) |
| Routing | React Router (rutas cliente), Laravel sirve un único Blade catch-all `/{any}` | SPA pura; el backend solo expondrá `/api/v1/*` |
| Estado remoto | TanStack Query | Decisión del plan maestro; polling y cache declarativos |
| Estado local | `useState`/contexto mínimo (drawer abierto, chip activo, paso de asignación) | Sin Redux (plan maestro §8) |
| Mock de API | **MSW (Mock Service Worker)** interceptando `fetch` en dev, activado por `VITE_USE_MOCKS=true` | Las vistas consumen `fetch('/api/v1/...')` real; apagar mocks = conectar backend sin tocar componentes |
| Estilos | CSS propio con variables (tokens de la sección 10 de la Guía Técnica). **Sin Tailwind ni librería de componentes** | El design system está cerrado y especificado al píxel; una librería externa pelearía contra él |
| Tipografías | IBM Plex Sans e IBM Plex Mono **self-hosted** (`@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono`) | Sin dependencia de CDN en una herramienta operativa |
| Idioma UI | Español (como la maqueta) | Es el idioma del equipo de soporte |

Dependencias npm (cerradas para F0–F6; agregar otra requiere justificación):

```text
react, react-dom, react-router-dom, @tanstack/react-query,
msw (dev), @fontsource/ibm-plex-sans, @fontsource/ibm-plex-mono,
typescript, vite, laravel-vite-plugin, @vitejs/plugin-react
```

## 2. Estructura de código

Refleja la estructura sugerida por la Guía Técnica (§9) y el plan maestro (§03-8), en TypeScript:

```text
resources/js/
├── app/
│   ├── main.tsx              # bootstrap: QueryClient, Router, MSW si VITE_USE_MOCKS
│   ├── router.tsx            # rutas: /, /agents, /agents/assign, /runs, /audit, /clients, /catalog, /login
│   └── queryClient.ts
├── api/
│   ├── client.ts             # fetch con baseURL /api/v1 + bearer + envoltura {data,page,total} + errores
│   ├── endpoints.ts          # una función tipada por endpoint (sección 3 de la Guía Técnica)
│   └── types.ts              # Agent, Run, Command, Client, SyncCatalogItem, AuditEvent, enums
├── mocks/
│   ├── handlers.ts           # MSW: implementa TODOS los endpoints con el contrato exacto
│   ├── fixtures/             # datos de la maqueta (agentes, runs, auditoría, clientes, catálogo)
│   └── browser.ts
├── lib/
│   ├── status.ts             # meta(status) → {label,bg,fg,dot} — ÚNICA fuente de color de estado
│   ├── format.ts             # ISO→relativo ("hace 12 s"), duración, números
│   └── errors.ts             # código → {opMsg, techMsg?, action, retryable}
├── components/
│   ├── StatusBadge.tsx  Table.tsx  FilterBar.tsx  Chip.tsx
│   ├── Drawer.tsx  Card.tsx  Button.tsx  Notice.tsx
│   ├── KpiCard.tsx  CodeBlock.tsx  Skeleton.tsx  EmptyState.tsx  ErrorState.tsx
├── layout/
│   ├── AppShell.tsx          # sidebar + topbar + <Outlet/>
│   ├── Sidebar.tsx           # 242px navy, grupos Operación/Configuración, "Agentes" expandible
│   └── Topbar.tsx            # título/subtítulo, buscador global, badge PROD, refrescar
├── views/
│   ├── dashboard/  agents/  assign/  runs/  audit/  clients/  catalog/  login/
└── styles/
    ├── tokens.css            # variables de la sección 10 de la Guía Técnica
    └── base.css
```

**Reglas duras (violación = rechazo en review):**

1. Ningún color de estado ni formato de fecha escrito a mano dentro de una vista: todo sale de `status.ts` / `format.ts` / `errors.ts`.
2. El backend (y los mocks) solo envían claves de estado crudas (`"online"`, `"failed"`…) y fechas ISO 8601 UTC; el frontend resuelve label/color/relativo.
3. Estado desconocido cae al badge gris "Deshabilitado" (nunca rompe la UI).
4. Todo listado usa la envoltura `{ data, page, page_size, total }`; todo error usa `{ error: { code, message } }`.
5. Detalle = drawer de 560px con cabecera navy; nunca modal centrado ni página nueva. Un solo drawer abierto a la vez.
6. Vista de listado nueva = FilterBar (buscador + chips + contador) + Table o grilla de tarjetas. Nada más.

## 3. Contratos congelados antes de codificar (Fase F0)

Copiar tal cual desde la Guía Técnica a `api/types.ts` + `lib/status.ts` + `lib/errors.ts`:

- **Enums:** agent `online|offline|enrolled|disabled` · run `success|running|failed|skipped` · command `pending|completed|failed|expired|skipped` · sync `enabled|paused|disabled` · client health `ok|warning|error|enrolled` · trigger `schedule|manual|command` · command type `run_now|stop_run|pause_sync|resume_sync|refresh_config` · audit kind `command|event|error|config|auth`.
  - Nota: la Guía Técnica omite `stop_run` en command type, pero el plan maestro lo define como comando MVP (ADR-005) y la UI de ejecución `running` necesita el botón "Detener". **Se incluye `stop_run` desde el inicio.**
- **Tokens:** navy `#00133C`, accent `#278AC5`, deepBlue `#002B86`, appBg `#EEF0F3`, surface `#FFFFFF`, border `#E2E6EB`, rowBorder `#EDEFF2`, text `#152238`, text2 `#5A6472`, text3 `#8A929C`; estados verde/rojo/azul/ámbar/gris con sus tríos dot/bg/fg.
- **Códigos de error** con `retryable`: `SOURCE_CONNECTION_FAILED`(sí), `CENTRAL_API_UNAVAILABLE`(sí), `SYNC_ALREADY_RUNNING`(sí), `SCHEMA_CHANGED`(no), `AUTHENTICATION_FAILED`(no), `INVALID_CONFIG`(no) — extensible con la lista completa del plan maestro §04-7.
- **Endpoints** (los mocks implementan todos): `POST /auth/login`, `GET /dashboard/metrics`, `GET /agents`, `GET /agents/{code}`, `POST /agents/{code}/commands`, `PATCH /agents/{code}/syncs/{sync_code}`, `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/retry`, `GET /audit`, `GET /clients`, `GET /clients/{id}`, `GET /syncs`, `POST /syncs`, `PATCH /syncs/{code}`.

## 4. Fases de implementación

Cada fase termina con una vertical slice navegable (mismo principio del plan maestro). Estimación orientativa entre paréntesis.

### F0 — Scaffold y contratos (0.5–1 día)

- [ ] `composer create-project laravel/laravel .` (o carpeta `center/` si se prefiere separar del repo de docs) — anotar versión instalada.
- [ ] Vite + React + TS (`laravel-vite-plugin`, `@vitejs/plugin-react`, `tsconfig` estricto, alias `@/`).
- [ ] Ruta Blade catch-all que monta la SPA; `npm run dev` con Herd sirviendo el sitio.
- [ ] `styles/tokens.css` + fuentes IBM Plex + reset base.
- [ ] `api/types.ts`, `lib/status.ts`, `lib/format.ts`, `lib/errors.ts` (contratos de la sección 3).
- [ ] MSW instalado y arrancando con `VITE_USE_MOCKS=true`.

**Exit:** la app carga en el navegador, TypeScript compila estricto, un `fetch('/api/v1/dashboard/metrics')` de prueba responde desde MSW.

### F1 — Shell y design system (1–2 días)

- [ ] `Sidebar` (242px navy, grupos, "Agentes" expandible con chevron 0.18s, contadores, colapso off-canvas <860px con hamburguesa).
- [ ] `Topbar` (título+subtítulo por ruta, buscador global, badge PROD con pulso, botón refrescar con giro 0.9s).
- [ ] Componentes base: `Card`, `Table`, `StatusBadge`, `Chip`, `FilterBar`, `Button` (primario/secundario), `Drawer` (560px, scrim, cabecera navy, un solo abierto), `Notice`, `CodeBlock` (navy + texto `#9FE0C0`), `KpiCard`, `Skeleton`, `EmptyState`, `ErrorState`.
- [ ] Router con las 8 rutas y placeholders.

**Exit:** navegación completa funcionando; los componentes replican la maqueta al píxel (comparar lado a lado con el standalone).

### F2 — Mock API completa (1 día)

- [ ] Fixtures con los datos de la maqueta (42 agentes ⇒ generar variaciones realistas a partir de los 5–8 visibles).
- [ ] Handlers MSW para los 15 endpoints: filtros `?status=&search=`, paginación `?page=&page_size=`, envoltura estándar, errores `{error:{code,message}}`, latencia simulada (200–500 ms) y modo error forzable (para probar `ErrorState`).
- [ ] Mutaciones con efecto en memoria: `POST commands` crea comando `pending` que transiciona a `completed` a los ~5 s (permite ver el poll de estado de comando); `PATCH syncs` cambia estado/intervalo; `POST retry` crea un run nuevo `running` que termina en `success|failed`.

**Exit:** toda la API navegable con curl/DevTools; los estados transicionan solos (comandos, runs running→terminal).

### F3 — Vistas de lectura (3–4 días)

Orden: **Dashboard → Ejecuciones → Agentes ▸ Listado → Auditoría → Clientes → Catálogo**.

- [ ] **Dashboard:** strip de 5 KPIs + grilla 2×2 (Agentes recientes, Auditoría reciente, Últimas ejecuciones, Sincronizadores asignados) + enlaces "Ver todos →" que navegan con filtro aplicado. Polling 15 s.
- [ ] **Ejecuciones:** chips Todas/Success/Failed/Running, contador, aviso informativo, tabla de 10 columnas (RUN, cliente, sync, estado, trigger, inicio, dur., leídas, ins/upd/fail, error). Duración calculada en front desde `started_at/ended_at`.
- [ ] **Agentes ▸ Listado:** chips por estado de agente, tabla (código mono azul, cliente, máquina, versión, estado, heartbeat relativo, IP, syncs, último error).
- [ ] **Auditoría:** filtros por `kind` + fecha, lista con ícono coloreado por categoría, actor, target mono, contexto, resultado, timestamp.
- [ ] **Clientes:** grilla de tarjetas (nombre, sistema, salud, KPIs agentes/syncs, última sync, badge de errores abiertos).
- [ ] **Catálogo:** grilla de tarjetas de sincronizadores (nombre, código mono, descripción, versión mínima, key, estado, intervalo).
- [ ] Los 4 estados de red en cada vista: skeleton con la misma geometría, vacío neutro, error rojo con "Reintentar", 403 oculta contenido.

**Exit:** todas las listas navegan, filtran y buscan contra los mocks; estados de red demostrables (modo error de MSW).

### F4 — Drawers y acciones (3–4 días)

- [ ] **Drawer de ejecución:** métricas (leídas/insertadas/actualizadas/fallidas, trigger, duración), timeline de eventos con tono de color, bloque "Manejo del error" (código + badge reintentable, mensaje OPERATIVO, TÉCNICO en mono, ACCIÓN SUGERIDA en aviso azul), botones "Reintentar ejecución" (solo si `retryable`) y "Marcar revisado", "Payload resumido" en CodeBlock, correlation ID. Para run `running`: botón "Detener" (`stop_run`) y estado `stopping`.
- [ ] **Drawer de agente:** cabecera navy con código+estado, ficha (cliente, máquina, versión, IP, heartbeat), "Configuración activa" en CodeBlock, outbox (pending/sent), syncs asignados con toggle pausa/reanudar e intervalo (`PATCH`), comandos recientes con estado, runs recientes, timeline; acciones `run_now`, `refresh_config`, `pause_sync`/`resume_sync`.
- [ ] **Drawer de cliente:** ficha + agentes del cliente + runs recientes.
- [ ] **Drawer de alta de catálogo** ("Nuevo sync"): formulario con validación (código único, semver, intervalo ≥ 60 s) → `POST /syncs`; editar/deshabilitar existente → `PATCH`.
- [ ] **Asignación (2 pasos):** paso 0 grilla de selección de agente, paso 1 tabla de permisos por sync con "Cambiar agente" para volver. No colapsar en un paso.
- [ ] **Comandos end-to-end (con mocks):** al enviar un comando, badge `pending` + poll cada 5 s hasta terminal; deshabilitar el botón mientras hay uno pendiente del mismo tipo.
- [ ] Polling: ejecuciones visibles `running` cada 10 s (parar si no hay ninguna); estado de comando 5 s; dashboard 15 s.

**Exit:** el flujo demo completo funciona sin backend: ver agente → `run_now` → comando pending→completed → run running→success/failed → abrir drawer del run fallido → reintentar. Equivale a la maqueta pero con datos vivos.

### F5 — Login y sesión (0.5–1 día)

- [ ] Vista de login (marca BAPS sobre navy) → `POST /auth/login` (mock) → guardar bearer, adjuntarlo en `client.ts`.
- [ ] Guard de rutas: sin token → `/login`; respuesta 401 → limpiar sesión y redirigir; 403 → ocultar acción/vista.

**Exit:** sesión simulada completa; el interceptor queda listo para Sanctum/token real.

### F6 — QA de frontend (1–2 días)

- [ ] Checklist de estados del plan maestro §06 (fila Frontend): loading, empty, error, retry, pending, expired, failed, stopping, offline.
- [ ] Responsive: sidebar off-canvas <860px; tablas con scroll horizontal en su contenedor.
- [ ] Revisión de fidelidad contra la maqueta, vista por vista.
- [ ] Accesibilidad básica: foco visible, drawer con Escape y focus-trap, contraste de badges.
- [ ] Verificar que **ningún** color/formato quedó hardcodeado fuera de `lib/`.

**Exit del proyecto front:** demo navegable completa con mocks; `VITE_USE_MOCKS=false` deja la app apuntando a `/api/v1` real esperando el backend.

## 5. Conexión futura con el backend (fuera de alcance ahora)

Cuando se implemente el backend (fases 3 y 8 del plan maestro):

1. Implementar en Laravel los 15 endpoints con **exactamente** el contrato que ya cumplen los mocks (los handlers MSW sirven de especificación ejecutable y de referencia para los tests de Laravel).
2. Auth real (Sanctum tokens) reemplaza el login mock; el interceptor no cambia.
3. Apagar MSW (`VITE_USE_MOCKS=false`) — las vistas no se tocan.
4. Los fixtures de mocks se reutilizan como seeders/factories de desarrollo en Laravel.

## 6. Riesgos y decisiones abiertas

| Riesgo / decisión | Mitigación / criterio |
|---|---|
| Desalineación Guía Técnica vs plan maestro (ej. `stop_run`, detalle de cliente por `{name}` vs `{id}`) | Este plan fija: incluir `stop_run`; usar `{id}` numérico para clientes. Registrar cualquier otra discrepancia en el ADR antes de codificar |
| Laravel "13" aún no verificado en el entorno | `composer create-project` instala la última estable; si difiere, se anota en README sin cambiar el plan |
| Fidelidad visual | La maqueta standalone es el árbitro; comparar lado a lado en cada PR de vista |
| Alcance de RBAC en front | MVP: un solo rol operativo; el guard de 403 queda implementado pero sin matriz de permisos |
| Buscador global de la topbar | MVP: filtra dentro de la vista activa (no búsqueda federada); dejar TODO para versión federada |

## 7. Orden de PRs sugerido

```text
1. front-scaffold-laravel-vite-react     (F0)
2. front-tokens-design-system            (F1 componentes)
3. front-shell-sidebar-topbar-router     (F1 layout)
4. front-mock-api-msw                    (F2)
5. front-dashboard                       (F3)
6. front-runs-list                       (F3)
7. front-agents-list                     (F3)
8. front-audit-clients-catalog           (F3)
9. front-run-drawer-error-handling       (F4)
10. front-agent-drawer-commands          (F4)
11. front-assign-flow-catalog-forms      (F4)
12. front-login-session-guards           (F5)
13. front-qa-states-responsive           (F6)
```

Total estimado: **10–14 días de desarrollo efectivo** para el front funcional completo con mocks.
