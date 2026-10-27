# Componentes implementados

## Centro Laravel

### Stack

- PHP `^8.3`; entorno de verificación con PHP 8.4.23.
- Laravel `^13.8`.
- Sanctum `^4.3`.
- PHPUnit `^12.5.12` y Pint `^1.27`.
- Persistencia productiva configurada para MySQL; pruebas con SQLite efímero.

### API vigente

La aplicación registra 36 rutas totales: 31 de API, 5 de framework/web. Las 31 rutas de producto se dividen en 6 rutas de agente y 25 rutas de control.

Agente:

- enrolamiento;
- heartbeat;
- descarga de configuración;
- claim de comandos;
- resultado de comando;
- ingestión de eventos.

Control:

- login;
- métricas de dashboard;
- listados y detalle de agentes, runs, clientes y auditoría;
- comandos y consulta de sus resultados;
- asignación/configuración de sincronizadores;
- configuración cifrada de MySQL BAPPS;
- retry y review de fallos;
- CRUD de catálogo y fuentes;
- publicación versionada de recetas.

### Patrones operativos verificados

- Acciones separadas para transacciones e invariantes relevantes.
- Recursos API para las vistas de control.
- Eager loading y agregados en endpoints de lectura principales.
- Auditoría de mutaciones y comandos sin incluir secretos deliberadamente.
- Retiro del catálogo solo después de deshabilitarlo: elimina sus asignaciones, incrementa la versión de configuración de los agentes afectados y conserva el historial mediante soft delete.
- Recetas inmutables por versión y hash de payload.
- Configuración de agente incrementada ante cambios para forzar convergencia.

### Límites

- Payload de agente: 65.536 bytes.
- Enrolamiento/login: 10 solicitudes por minuto.
- Rutas autenticadas del agente: 120 por minuto.
- Token de control: una sesión activa por usuario, capacidad única `control-api`, 8 horas.
- No hay endpoint de logout/revocación explícito; un login nuevo borra tokens anteriores del mismo nombre y la UI elimina el token local al recibir 401.

## Frontend React

### Stack y estructura

- React/React DOM `19.2.7`.
- React Router `7.18.1`.
- TanStack Query `5.101.2`.
- TypeScript `7.0.2`.
- Vite `8.1.5` observado en build.
- MSW `2.15.0` opcional.

La aplicación tiene rutas para login, dashboard, agentes, asignación, ejecuciones, auditoría, clientes y catálogo. La autenticación cliente se basa en la presencia de un bearer en `localStorage`; el servidor sigue siendo la autoridad real.

### Capacidades visibles

- Dashboard con refresco cada 15 segundos.
- Listados paginados, filtros, skeletons, estados vacíos y errores reintentables.
- Drawers de agentes y runs.
- Ejecución, pausa, reanudación, detención, revisión y retry.
- Asignación por sistema/versión/motor.
- Configuración de escritores con URL y token privado.
- Alta/edición/retiro de fuentes y sincronizadores.
- Constructor de receta de lectura y receta de escritura.
- Inspección de tabla a través del comando remoto.
- Sistema visual centralizado de estados, formatos y errores.

### Estado técnico

El build de producción pasa, pero Vite transpila TypeScript sin efectuar el chequeo estricto completo. El typecheck falla en `resources/js/mocks/db.ts` y `resources/js/mocks/handlers.ts`: siete objetos de catálogo antiguos no incluyen `direction`. No hay suite automatizada de componentes o E2E en el repositorio.

## Agente Windows

### Distribución

El instalador NSIS copia GUI y servicio, crea accesos del menú Inicio, repara permisos del directorio de estado, instala opcionalmente un bundle de confianza Ed25519, migra datos DPAPI antes de ejecutar como `LocalSystem`, instala `BAPPSyncAgent` con inicio automático y soporta actualización/desinstalación.

La firma de código Authenticode no está incorporada al artefacto `0.7.10`.

### Runtime

- Instancia única por lock del sistema operativo.
- Servicio Windows bajo SCM.
- Scheduler monotónico: la primera ejecución ocurre después del intervalo, no al arrancar.
- Intervalos normalizados entre 60 y 86.400 segundos.
- Un solo worker por agente.
- Config activa y última válida.
- Backoff/jitter para Centro y outbox.
- Recuperación de eventos `sending` y runs interrumpidos tras reinicio.
- Redacción de contraseñas/tokens en errores reportados.
- Registro operativo auxiliar en `sync_success` y `sync_errors` de MySQL BAPPS; la outbox sigue siendo la autoridad.

### Conectividad y secretos

- Firebird mediante `firebirdsql`, charset configurable y aislamiento snapshot en lecturas.
- SQL Server mediante ODBC Driver 18, `Encrypt=yes` y `TrustServerCertificate=no`.
- MySQL mediante PyMySQL.
- Token de agente, passwords de fuente/MySQL y token de pedidos protegidos con DPAPI de máquina.
- Claves Ed25519 confiables ancladas en identidad, con transición firmada para rotación.

### Sincronizadores registrados

| Motor/código | Naturaleza | Estado |
|---|---|---|
| `clientes_valery` | Implementación especializada, Firebird a MySQL con upsert | `IMPLEMENTADO` |
| `declarative_table_reader` | Motor genérico por receta para Firebird/SQL Server a MySQL | `PARCIAL` |
| `valery_prs_writer_v1` | Escritor especializado API de pedidos a Firebird Valery | `PENDIENTE_ACEPTACION` |

### Observación importante

El instalador y los ejecutables portables se pudieron verificar, pero el entorno `.venv` no es reproducible tal como está: `pyvenv.cfg` referencia `C:\Users\USUARIO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`, que ya no existe. Debe recrearse con un Python soportado antes del siguiente release.
