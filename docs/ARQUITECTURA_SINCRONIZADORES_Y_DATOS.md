# Sincronizadores y bases de datos

## Separación obligatoria

Hay tres almacenes con responsabilidades distintas. No se intercambian ni se
reutilizan credenciales entre ellos.

| Capa | Ubicación | Responsabilidad |
|---|---|---|
| Centro BAPPS Sync | MySQL `bapps_sync` | Usuarios, agentes, configuración, comandos, eventos, ejecuciones, auditoría y tokens Sanctum. |
| Fuente del cliente | Firebird Valery | Datos de negocio de origen; el agente la consulta en modo lectura. |
| Destino del cliente | MySQL BAPPS | Datos sincronizados y logs operativos locales del cliente. |

El estado transitorio del agente (`outbox`, configuración activa, journal y
estado de ejecuciones) permanece en archivos protegidos bajo
`C:\ProgramData\Bapps\SyncAgent`; no es una base central ni sustituye MySQL.

## Dónde vive la lógica de sincronización

Cada sincronizador pertenece al paquete del agente:

```text
agent/src/bapps_sync_agent/syncs/
├── protocol.py          # Contrato: run(context) -> SyncResult
├── registry.py          # Resolución segura por sync_code
├── builtins.py          # Registro único de sincronizadores incluidos
└── clientes_valery.py   # Implementación Firebird Valery -> MySQL BAPPS
```

`clientes_valery.py` solo contiene la lógica funcional: conexión al destino
MySQL antes de abrir Firebird, lectura `SELECT` de `CLIENTES`, normalización y
upsert idempotente por `CODIGO`. El runtime crea el registro mediante
`create_builtin_synchronizer_registry()` en `application/runtime.py`.

Para agregar un sincronizador **empaquetado con lógica propia** se debe:

1. Crear `syncs/<codigo>.py` con una clase que implemente `run(SyncContext) -> SyncResult`.
2. Declarar una constante `CODE` igual al `sync_catalog.code` central.
3. Registrarlo exclusivamente en `syncs/builtins.py`.
4. Añadir sus pruebas unitarias/integración y el catálogo/asignación desde el Centro.

Una receta declarativa de lectura directa no crea un archivo Python ni una
entrada nueva por tabla en `builtins.py`: todas se resuelven mediante el motor
genérico incluido y probado en el instalador.

No se admite lógica de negocio de sincronización en controladores Laravel ni en
la SPA; Laravel gobierna y proyecta, el agente ejecuta localmente.

## Recetas declarativas y módulos empaquetados

La siguiente evolución conserva esa frontera y separa dos mecanismos:

1. **Recetas de lectura:** el instalador incorpora un motor genérico de
   fotografía de tablas y conectores aprobados. El Centro selecciona tabla,
   columnas, filtros estructurados, alcance padre/renglón, destino e intervalo
   y entrega únicamente JSON firmado. El agente no descarga ni ejecuta código.
2. **Módulos empaquetados:** pedidos de escritura, joins, cálculos y reglas de
   negocio se desarrollan manualmente, se prueban y se incluyen en una nueva
   versión del instalador. La asignación web solo los activa/configura.

El estándar de lectura construye una tabla sombra completa en el MySQL destino,
la valida y la intercambia atómicamente con una tabla administrada por BAPPS
Sync. El nombre es configurable para preservar contratos legacy. No usa
`TRUNCATE` sobre la tabla activa. La especificación exacta del motor único y su
contrato están en
`docs/ESPECIFICACION_MOTOR_UNICO_LECTURA_PROFIT_2026-07-27.md`; los blindajes y
el orden de trabajo están en
`docs/PLAN_RESILIENCIA_Y_RECETAS_LECTURA_2026-07-27.md`.

## Migración de la central Laravel a MySQL

Las instalaciones nuevas usan MySQL por defecto. Configure en `.env` de la
máquina que ejecuta Laravel:

```dotenv
DB_CONNECTION=mysql
DB_HOST=<host-mysql-central>
DB_PORT=3306
DB_DATABASE=bapps_sync
DB_USERNAME=<usuario-restringido>
DB_PASSWORD=<secreto>
DB_CHARSET=utf8mb4
DB_COLLATION=utf8mb4_unicode_ci
```

La cuenta debe tener permisos únicamente sobre `bapps_sync`. Después se ejecuta:

```powershell
php artisan config:clear
php artisan migrate --force
```

La SQLite histórica fue transferida a MySQL el 2026-07-27 mediante
`bapps:copy-central-sqlite-to-mysql`; se conserva como respaldo de origen, no
como central operativa. Las pruebas automatizadas siguen usando SQLite en
memoria, definido en `phpunit.xml`, de forma intencional.
