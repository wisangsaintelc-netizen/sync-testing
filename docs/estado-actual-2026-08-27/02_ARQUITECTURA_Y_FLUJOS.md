# Arquitectura y flujos certificados

## Topología vigente

```text
Navegador / operador
        |
        | HTTPS + Bearer Sanctum
        v
Centro Laravel 13 + SPA React 19
        |
        +-- MySQL central: control, configuración, eventos y auditoría
        |
        | HTTPS + X-Agent-Code + Bearer de agente
        v
Agente Windows 0.7.10 (servicio, un worker)
        |
        +-- Estado local en C:\ProgramData\Bapps\SyncAgent
        |   identidad, configuración, perfiles, outbox, journal y runs
        |
        +-- Firebird / SQL Server del sistema administrativo
        |
        +-- MySQL BAPPS local del cliente
        |
        +-- API privada de pedidos (solo escritor PRS)
```

## Responsabilidades

### Centro

El Centro es plano de control y observabilidad. Guarda catálogo, fuentes lógicas, asignaciones, versiones de receta, comandos, runs, eventos y auditoría. Firma la configuración cuando existe una clave Ed25519 válida. No abre conexiones a las bases del cliente ni ejecuta SQL de extracción.

### Agente

El agente es plano de datos. Conserva las credenciales locales, conecta a los motores del cliente, ejecuta el trabajo, publica en MySQL BAPPS o escribe PRS en Firebird, y reporta telemetría. El runtime usa un `ThreadPoolExecutor(max_workers=1)`: los syncs de un mismo agente quedan serializados.

### Frontend

La SPA consume exclusivamente `/api/v1` mediante un cliente HTTP centralizado. MSW continúa disponible como modo de desarrollo, pero `.env.example` establece `VITE_USE_MOCKS=false` y el backend real ya existe.

## Almacenes de datos

| Almacén | Contenido | Protección/propiedad |
|---|---|---|
| MySQL central | Usuarios/tokens, clientes, agentes, catálogo, fuentes, asignaciones, recetas, comandos, eventos, runs y auditoría | Laravel; secretos de destino y escritor usan casts `encrypted:array` ligados a `APP_KEY`. |
| Firebird/SQL Server fuente | Tablas del sistema administrativo | Solo el agente accede con perfiles locales. Identificadores se validan y valores se parametrizan. |
| MySQL BAPPS cliente | Tablas materializadas y bitácoras operativas | El motor declarativo registra ownership en `__bapps_sync_managed_tables`. |
| Firebird Valery destino | Presupuestos PRS y maestros consultados | Escritura especializada en una transacción; idempotencia por orden de compra. |
| Estado local Windows | Token de agente, perfiles, config activa/última válida, outbox, journal, estado de runs y runtime | Archivos atómicos; secretos con DPAPI `LocalMachine`; permisos reparados por instalador. |

## Flujos de control

### Enrolamiento

1. El Centro debe tener un agente habilitado y un token de enrolamiento hasheado.
2. El agente presenta código, token, equipo y versión.
3. El Centro rota la credencial y devuelve un token aleatorio de 32 bytes representado en hexadecimal.
4. Si la firma está configurada, devuelve también la clave pública Ed25519 y su `key_id`.
5. El agente protege el token localmente con DPAPI.

### Heartbeat y configuración

- Heartbeat nominal cada 30 segundos, con jitter.
- El Centro considera online durante 120 segundos desde `last_seen_at`.
- El agente informa versión, configuración activa, runs y tamaño/cantidad de outbox.
- Una diferencia de versión fuerza descarga.
- La configuración no válida conserva la última copia válida y entra en retry exponencial hasta 300 segundos.
- Se rechaza bajar silenciosamente el número de versión.

### Comandos

- El agente consulta nominalmente cada 5 segundos y reclama hasta 5.
- El Centro da leases de 120 segundos, reencola leases vencidos y expira comandos fuera de plazo.
- Tipos actuales: `run_now`, `stop_run`, `pause_sync`, `resume_sync`, `refresh_config`, `inspect_source_table`.
- El journal local hace idempotente la ejecución por `command_id`; el Centro conserva el primer resultado terminal.
- Inspección: solo agente online, nombres allowlist, posición 1–10.000, máximo 256 columnas y muestras de texto truncadas a 500 caracteres. El resultado expira en cinco minutos y se purga periódicamente.

### Eventos y runs

El agente persiste `run_started` antes de tocar la fuente y `run_finished` al terminar. La outbox usa archivos, `fsync`, rename atómico, estados `pending/sending/failed` y retry exponencial con jitter. El Centro deduplica globalmente por `event_id` y proyecta eventos de run en `sync_runs`; un `run_started` tardío no revierte un estado terminal.

## Flujo de lectura declarativa

Estado: `PARCIAL`, con núcleo seguro implementado.

1. Verifica configuración y versión mínima.
2. Abre primero MySQL destino para no cargar la fuente cuando el destino no está disponible.
3. Comprueba que la tabla es administrable y que la versión de receta no retrocede.
4. Abre Firebird con aislamiento snapshot o SQL Server con transacción `SNAPSHOT`.
5. Compila SQL desde una gramática cerrada; no admite SQL crudo ni `SELECT *` en recetas.
6. Lee por lotes, crea una tabla `__bapps_new_<hash>` y carga el snapshot.
7. Verifica el conteo de filas.
8. Publica por rename atómico y elimina el backup controlado.

Lo que **no** hace aún el runtime: verificar `schema_fingerprint`; aplicar `profit.article_tax_rate_v1`; distinguir `daily_history_v1` de un snapshot; usar `key_columns`; imponer `statement_timeout_seconds` o `max_runtime_seconds`.

## Flujo del escritor PRS

Estado: `PENDIENTE_ACEPTACION`.

1. Verifica la configuración disponible y localiza asignación, opciones y token.
2. Reclama un solo pedido mediante lease en `/api/private/bapps-sync/v1/order-jobs/claim`.
3. Conecta al perfil Firebird y verifica tablas/campos e índices mínimos.
4. Si ya existe `PRS + ORDEN_DE_COMPRA`, devuelve el documento existente sin duplicarlo.
5. Lee monedas `01` y `02`, cliente, vendedor y productos.
6. Rechaza pedidos sin productos, descuentos en v1, factores no positivos y maestros inexistentes.
7. Reserva correlativo, documento PRS y números de línea, con reintento ante colisiones.
8. Inserta cabecera, auxiliares, detalles y texto dentro de una transacción.
9. Normaliza y valida totales antes del commit.
10. Completa o falla el job en la API de pedidos, clasificando reintentos.

La cabecera se guarda en moneda principal `01`; el cálculo autorizado parte de precios USD con impuesto y factor de moneda `02`. La vigencia es de 15 días. Existe una tolerancia explícita para instalaciones legacy que fuerzan a cero campos fiscales derivados del detalle, mientras siguen validándose estrictamente cantidades, netos, totales y cabecera.
