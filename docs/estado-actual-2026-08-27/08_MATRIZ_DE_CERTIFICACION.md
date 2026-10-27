# Matriz de certificación

Esta matriz evita convertir una intención documental en un hecho. La evidencia citada es la fuente primaria dentro del repositorio.

| Elemento | Veredicto | Evidencia primaria | Observación |
|---|---|---|---|
| SPA servida por Laravel | `IMPLEMENTADO` | `routes/web.php`, `resources/js/app/router.tsx` | Catch-all web y rutas protegidas del cliente. |
| API de agente | `IMPLEMENTADO/PROBADO` | `routes/api.php`, `tests/Feature/AgentApiTest.php` | Seis endpoints autenticados/limitados. |
| API de control | `IMPLEMENTADO/PROBADO` | `routes/api.php`, tests Feature | 25 rutas contando login. |
| Persistencia central | `IMPLEMENTADO/PROBADO` | `database/migrations`, modelos, tests | MySQL productivo; SQLite en pruebas. |
| Login real | `IMPLEMENTADO/PROBADO` | `LoginController`, `ControlApiReadTest` | Token Sanctum de 8 horas. |
| Logout remoto | `NO_IMPLEMENTADO` | rutas/controladores | Solo limpieza local al 401 o revocación por login nuevo. |
| RBAC admin/operator | `NO_IMPLEMENTADO` | `User`, middleware, migraciones | Capacidad única; rol fijo. |
| Dashboard operacional | `IMPLEMENTADO/PROBADO` | `DashboardMetricsController`, `Dashboard.tsx` | Refresco cliente cada 15 s. |
| Gestión de agentes | `IMPLEMENTADO/PROBADO` | `AgentController`, recursos, vistas | Listado, detalle y estado derivado. |
| Gestión de clientes | `IMPLEMENTADO/PROBADO` | `ClientController`, recursos, vistas | Salud derivada de agentes/fallos. |
| Gestión de runs | `IMPLEMENTADO/PROBADO` | `RunController`, acciones retry/review | Historial y revisión sin borrar fallos. |
| Auditoría de control | `IMPLEMENTADO/PROBADO` | `RecordControlAudit`, `AuditController` | No equivale a una bitácora completa de autenticación. |
| CRUD de fuentes | `IMPLEMENTADO/PROBADO` | `SyncSourceController`, tests catálogo | Fuente lógica, no credenciales remotas. |
| CRUD/retiro de catálogo | `IMPLEMENTADO/PROBADO` | `SyncCatalogController`, `RetireSyncCatalog` | Código inmutable y retiro con historia preservada. |
| Publicación versionada de receta | `IMPLEMENTADO/PROBADO` | `PublishSyncRecipe`, tests catálogo | Transacción, versión y hash. |
| Asignación de sync | `IMPLEMENTADO/PROBADO` | `AssignAgentSync`, tests mutación | Controla catálogo, agente y versión mínima. |
| Config MySQL cifrada | `IMPLEMENTADO/PROBADO` | `Agent` cast, test dedicado | Depende de conservar `APP_KEY`. |
| Inspección remota segura | `IMPLEMENTADO/PROBADO` | `SourceTableInspector`, tests Centro/agente | Sin RBAC diferenciado. |
| Enrolamiento/rotación | `IMPLEMENTADO/PROBADO` | `EnrollAgent`, tests | Devuelve token nuevo y posible trust inicial. |
| Heartbeat/online | `IMPLEMENTADO/PROBADO` | `AgentService`, `Agent` scopes, tests | 30 s nominal / 120 s de umbral. |
| Claim/lease de comandos | `IMPLEMENTADO/PROBADO` | `ClaimCommands`, tests | Lease 120 s, hasta 5. |
| Journal idempotente local | `IMPLEMENTADO/PROBADO` | `CommandJournal`, tests comando/estado | Conserva el primer resultado local. |
| Outbox durable | `IMPLEMENTADO/PROBADO_UNITARIO` | `Outbox`, tests estado/servicio | Sin cuota ni aceptación de disco lleno. |
| Recuperación tras restart | `IMPLEMENTADO/PROBADO_UNITARIO` | `RunStateStore`, `AgentService` | Emite run `interrupted`. |
| Scheduler automático | `IMPLEMENTADO/PROBADO_UNITARIO` | `IntervalScheduler` | Primera ejecución espera el intervalo. |
| Prevención de doble run | `IMPLEMENTADO/PROBADO_UNITARIO` | `SyncRunner` | Un worker y reserva por sync. |
| Stop cooperativo | `IMPLEMENTADO/PROBADO_UNITARIO` | `SyncRunner`, `SyncContext` | Depende de puntos `raise_if_stopped`. |
| Secretos locales DPAPI | `IMPLEMENTADO/PROBADO_UNITARIO` | `WindowsSecretProtector`, tests estado/fuente | Scope de máquina. |
| Firma Ed25519 del lector | `IMPLEMENTADO/PROBADO` | Centro signer, agente verifier, tests | Incluye rotación firmada. |
| Firma obligatoria del writer | `NO_IMPLEMENTADO` | `ConfigSignatureVerifier` | Solo detecta el engine declarativo de lectura. |
| SQL declarativo cerrado | `IMPLEMENTADO/PROBADO_UNITARIO` | `read_recipes.py`, `read_recipe_query.py` | Identificadores allowlist, valores parametrizados. |
| Snapshot consistente fuente | `IMPLEMENTADO/PROBADO_UNITARIO` | `DeclarativeTableReaderSynchronizer` | Firebird snapshot / SQL Server SNAPSHOT. |
| Shadow/swap destino | `IMPLEMENTADO/PROBADO_UNITARIO` | `SnapshotTablePublisher` | Conteo y rename antes de reemplazo. |
| Ownership de tablas | `IMPLEMENTADO/PROBADO_UNITARIO` | `__bapps_sync_managed_tables`, tests | Impide adoptar/sobrescribir tabla ajena. |
| Schema fingerprint | `SOLO_VALIDADO` | parser/schema | Nunca se compara con la fuente. |
| Daily history | `SOLO_VALIDADO` | parser | Ejecuta el mismo publicador snapshot. |
| Transformación fiscal Profit | `SOLO_VALIDADO` | parser | No se aplica al row. |
| Timeouts de receta | `SOLO_VALIDADO` | parser | No se conectan a cursor/runtime. |
| Parent scope/booleanos end-to-end | `PARCIAL` | schema/agente vs reglas Laravel | Agente compila; Centro no permite publicarlos completamente. |
| `clientes_valery` | `IMPLEMENTADO/PROBADO_UNITARIO` | sincronizador y tests | Camino especializado aún vigente. |
| Writer PRS | `IMPLEMENTADO/PENDIENTE_ACEPTACION` | `valery_prs_writer.py`, 18 tests de fuente | Falta prueba física final. |
| Idempotencia PRS | `IMPLEMENTADO/PROBADO_UNITARIO` | `_existing` y tests | Busca PRS + orden de compra. |
| Transacción PRS | `IMPLEMENTADO/PROBADO_UNITARIO` | `_write`, `_insert_prs` | Rollback ante fallo, commit tras validación. |
| API privada de pedidos servidor | `NO_VERIFICABLE_LOCALMENTE` | solo `OrdersApiClient` | El servidor está fuera del alcance. |
| Instalador/servicio 0.7.10 | `ARTEFACTO_VERIFICADO` | NSIS, EXE, auto-test | Hash/tamaño coinciden. |
| Authenticode | `NO_IMPLEMENTADO` | `Get-AuthenticodeSignature` | Estado `NotSigned`. |
| Suite Laravel | `PROBADO` | ejecución del corte | 48/48, 279 aserciones. |
| Suite Python | `NO_REEJECUTADA` | 106 métodos presentes | `.venv` no reproducible. |
| Build frontend | `PROBADO` | ejecución del corte | 115 módulos. |
| Typecheck frontend | `FALLA` | ejecución del corte | 7 mocks sin `direction`. |
| CI/CD | `NO_EVIDENCIADO` | inventario del repo | No hay pipeline visible. |
| Deploy productivo | `NO_VERIFICABLE_LOCALMENTE` | guía de deploy solamente | Requiere evidencia del ambiente. |
| Soak/escala 100 agentes | `NO_EVIDENCIADO` | planes QA | Objetivo, no resultado certificado. |
