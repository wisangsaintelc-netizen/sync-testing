# BAPPS Sync — handoff autoritativo (2026-07-27)

> Actualización 2026-07-29: la inspección de tablas desde el creador de
> sincronizadores ya está implementada mediante un agente online. Incluye
> navegación por registro y requiere agente 0.6.9; se documenta en
> `docs/CREAR_SINCRONIZADOR_DESDE_CATALOGO.md`. Instalador vigente:
> `agent/release/BAPPS-Sync-Setup-0.6.9.exe` (SHA-256
> `7842A4B3E2528D99AE115DF5CEECA1EEC1D2D584166C2E20FF4CE88C998EBEBA`).

Este es el punto de partida para el siguiente chat. Sustituye las referencias
históricas contradictorias de handoffs anteriores. Leer además
`docs/ONGOING.txt`, `docs/ARQUITECTURA_SINCRONIZADORES_Y_DATOS.md` y
`docs/BAPPS_SYNC_PLAN_MAESTRO_v1.1.md`. Para el siguiente bloque, leer además
`docs/PLAN_RESILIENCIA_Y_RECETAS_LECTURA_2026-07-27.md`.

Para desplegar el Centro, leer y ejecutar exclusivamente el procedimiento de
`docs/DEPLOY_CENTRO_LARAVEL.md`; incluye runtime PHP, secretos, migraciones,
validación y rollback. No confundirlo con el despliegue del agente Windows.

Para la validación integral sin afectar el agente Valery estable, seguir
`docs/PILOTO_INTEGRAL_VALERY.md`. Identifica los gates de código pendientes y
define agente/tabla de piloto, matriz de fallos y evidencia.

## Restricciones de operación

- Trabajar en `C:\Sync\Valery\bapps-sync`.
- La central Laravel opera en MySQL local `bapps_sync`. SQLite se conserva solo
  como respaldo histórico y para PHPUnit en memoria.
- Firebird Valery y MySQL BAPPS pertenecen a la vertical del cliente; no son la
  base central de Laravel.
- La lógica de sincronización real está en el agente, no en Laravel:
  `agent/src/bapps_sync_agent/syncs/clientes_valery.py`. El registro único de
  sincronizadores es `agent/src/bapps_sync_agent/syncs/builtins.py`.
- `AGT-VALERY-01` está estable en **0.5.4**, Online, y reporta heartbeat desde
  el servicio Windows. No reinstalar, modificar ni reconstruir el agente o su
  servicio sin autorización explícita del usuario.
- No simular caída/reconexión del Centro o del MySQL BAPPS sobre Valery sin
  acordar una ventana de prueba. Las pruebas locales de hardening no requieren
  intervenir esa PC.

## Estado probado de la vertical real

```text
Firebird Valery (CLIENTES)
  → BAPPS Sync Agent Windows
  → Centro Laravel/MySQL bapps_sync
  → MySQL BAPPS del cliente (clientes_valery_sync)
  → bitácoras locales sync_success / sync_errors
```

- El agente lee Firebird por `SELECT` y hace upsert idempotente por `codigo`.
- Validación integrada anterior: 369 registros, sin duplicados; la ejecución
  exitosa actualiza el destino MySQL BAPPS.
- El reintento seguro fue validado extremo a extremo con un `run_id`
  preasignado: origen fallido sintético → comando → agente 0.5.2+ → una sola
  ejecución `success` con 369 actualizaciones.
- La versión de panel se toma del `agent_version` recibido por heartbeat; en
  0.5.4 se corrigió el valor fijo histórico. El panel ya muestra 0.5.4.

## Arquitectura de datos y salud operativa

- MySQL `bapps_sync` almacena usuarios, tokens Sanctum, clientes, agentes,
  asignaciones, catálogo, fuentes, comandos, ejecuciones, eventos y auditoría.
- Sanctum emite un bearer revocable de operador, con vencimiento de ocho horas.
- `agents.status` es el último estado reportado, pero el estado visible se
  calcula con heartbeat: `online` exige `last_seen_at` de menos de 120 segundos
  (`BAPPS_SYNC_AGENT_ONLINE_THRESHOLD_SECONDS`); de lo contrario es `offline`.
- Esto se aplica a lista, filtros, drawer, dashboard y salud de cliente.
- Una ejecución Failed es inmutable. `Marcar revisado` persiste
  `reviewed_at/reviewed_by`, genera auditoría y la quita del conteo de alertas,
  sin transformar el resultado de la ejecución.

## Fuentes de sincronización y catálogo

La entidad `sync_sources` normaliza el origen compatible de cada
sincronizador:

| Campo | Uso |
|---|---|
| `system_name` | Sistema administrativo, opcional |
| `system_version` | Versión del sistema, opcional |
| `database_engine` | Motor de base de datos, obligatorio |
| `enabled` | Permite o bloquea el uso futuro de la fuente |

`sync_catalog.sync_source_id` es la relación operacional. El campo
`source_type` se conserva como etiqueta histórica de compatibilidad/lectura.

API autenticada del Centro:

```text
GET    /api/v1/sync-sources
POST   /api/v1/sync-sources
PATCH  /api/v1/sync-sources/{id}
DELETE /api/v1/sync-sources/{id}
```

Reglas cerradas:

1. Las fuentes se crean, editan, habilitan y deshabilitan desde `Gestionar
   fuentes` en Catálogo.
2. Una fuente puede eliminarse solo si no tiene sincronizadores. El backend
   responde `409 SOURCE_IN_USE`; la UI inhabilita el botón y explica el motivo.
3. Deshabilitar una fuente conserva catálogos existentes, pero impide crear o
   reasignar un catálogo a ella. La API hace cumplir esto mediante
   `Rule::exists(...)->where('enabled', true)`.
4. El payload público usa `source_id`; en creación se convierte a
   `sync_source_id` antes de persistir. Este defecto fue descubierto por la
   prueba de catálogo y ya está corregido en
   `SyncCatalogController::store()`.
5. La vista agrupa tarjetas de sincronizadores por fuente y el selector de alta
   ofrece solo fuentes habilitadas.

Migraciones ya aplicadas en MySQL:

- `2026_07_27_220000_create_sync_sources_table.php`
- `2026_07_27_230000_normalize_legacy_sync_sources.php`

La segunda normaliza el legado `firebird / firebird` a `Firebird`. El usuario
ejecutó posteriormente `php artisan migrate`: resultado `Nothing to migrate.`

Validación confirmada:

```text
php artisan test --filter=ControlApiCatalogMutationTest
PASS — 6 pruebas, 34 aserciones

./vendor/bin/pint --test app/Http/Controllers/ControlApi/SyncCatalogController.php tests/Feature/ControlApiCatalogMutationTest.php
PASS — 2 archivos
```

Archivos relevantes:

- `app/Models/SyncSource.php`, `app/Models/SyncCatalog.php`
- `app/Http/Controllers/ControlApi/SyncSourceController.php`
- `app/Http/Controllers/ControlApi/SyncCatalogController.php`
- `app/Http/Requests/ControlApi/StoreSyncCatalogRequest.php`
- `app/Http/Requests/ControlApi/UpdateSyncCatalogRequest.php`
- `app/Http/Resources/ControlApi/SyncSourceResource.php`
- `resources/js/views/catalog/Catalog.tsx`

## UX implementada

- Agentes: paginación real de backend; resumen visible incluso con una página.
- Drawers: comandos, ejecuciones y timeline paginados en bloques de diez.
- IDs RUN/CMD abreviados con valor completo como tooltip; fecha y hora local en
  listados de comandos y ejecuciones.
- `Actualizar configuración` encola `refresh_config`; el agente descargará la
  configuración vigente en el próximo sondeo. No ejecuta sync ni toca bases del
  cliente.
- Se corrigió el drawer que perdía el foco al escribir: `Drawer.tsx` mantiene
  una referencia estable de `onClose`.
- `ToastProvider` global muestra mensajes centrados abajo: verde para éxito,
  rojo para error, cierre manual y expiración automática. Ya se usa en crear,
  editar, habilitar, deshabilitar y eliminar fuentes; también al crear o cambiar
  estado de sincronizadores del Catálogo. Queda reutilizable en otras vistas.

## Tooltip de Warning — último cambio pendiente de validar en PHP

Un cliente Warning ahora entrega `health_reason`. Cuando tiene agentes no
operativos, la API informa por ejemplo:

```text
Agente sin conexión: AGT-DEMO.
```

`StatusBadge` lo muestra como tooltip al pasar el cursor y al recibir foco de
teclado. El mismo detalle llega al badge Warning de la cabecera del drawer del
cliente. El backend carga `nonOnlineAgents` explícitamente para evitar N+1.

Archivos modificados:

- `app/Models/Client.php`
- `app/Http/Controllers/ControlApi/ClientController.php`
- `app/Http/Resources/ControlApi/ClientListResource.php`
- `resources/js/api/types.ts`
- `resources/js/components/StatusBadge.tsx`
- `resources/js/components/Drawer.tsx`
- `resources/js/views/clients/Clients.tsx`
- `resources/js/mocks/handlers.ts`, `resources/js/mocks/db.ts`
- `resources/js/styles/components.css`
- `tests/Feature/ControlApiReadTest.php`

Confirmado para este último cambio:

```text
npx.cmd tsc --noEmit  PASS
npm.cmd run build     PASS
```

Validado el 2026-07-28 mediante el PHP explícito de XAMPP y el aprovisionador
de runtime. La regresión PHP ya no depende de PHP en PATH:

```powershell
& 'C:\xampp\php-8.4.23\php.exe' artisan test --filter=ControlApiReadTest
.\vendor\bin\pint --test app\Models\Client.php app\Http\Controllers\ControlApi\ClientController.php app\Http\Resources\ControlApi\ClientListResource.php tests\Feature\ControlApiReadTest.php
```

Ambos controles quedaron confirmados el 2026-07-28; Pint también incluyó los
archivos de autenticación/configuración tocados durante la validación del
runtime.

El usuario confirmó la verificación visual del tooltip Warning. No hay
migración nueva para este cambio.

El usuario confirmó la verificación visual del tooltip Warning el 2026-07-27.
La suite completa Laravel fue validada el 2026-07-28 (39 pruebas, 231
aserciones) y Pint pasó en los archivos Laravel afectados.

## Toasts de mutaciones ampliados (2026-07-27)

`useToast()` ya cubre las mutaciones que faltaban:

- guardar una asignación de sincronizador;
- emitir `refresh_config`, `run_now`, `stop_run`, `pause_sync` y `resume_sync`;
- reintentar una ejecución fallida;
- marcar una alerta como revisada.

Cada acción informa éxito y errores de API con su código y mensaje. Se
conservaron las invalidaciones de React Query y los errores por fila de la
vista de asignación. Validado en este entorno:

```text
npx.cmd tsc --noEmit  PASS
npm.cmd run build     PASS
```

Falta únicamente la comprobación manual de estos avisos en el navegador.

## Asignación categorizada por fuente (2026-07-27)

El paso 2 de Asignación ahora presenta los sincronizadores en esta jerarquía:

```text
Base de datos → Sistema administrativo → Versión del sistema → Sincronizadores
```

El detalle de agente expone `syncs[].source` con `database_engine`,
`system_name` y `system_version`. Laravel carga `syncs.catalog.source` de forma
anticipada para evitar N+1; los datos heredados sin fuente reciben etiquetas
explícitas de ausencia. Los mocks y `ControlApiReadTest` cubren el contrato.

Validado en este entorno:

```text
npx.cmd tsc --noEmit  PASS
npm.cmd run build     PASS
```

Queda validar `ControlApiReadTest` y Pint desde XAMPP/PHP, más la comprobación
visual de la nueva jerarquía en el navegador.

## Breadcrumbs globales (2026-07-27)

La aplicación muestra ahora una ruta de navegación inmediatamente debajo del
header. Usa rutas concretas y conserva como enlaces solo los destinos
navegables. La asignación incorpora el código de agente seleccionado a la URL,
para conservar ese contexto al recargar o usar Atrás. Ejemplos:

```text
Inicio / Ejecuciones
Inicio / Listado
Inicio / Asignación / AGT-VALERY-01
Inicio / Catálogo de sincronizadores
```

En pantallas móviles se conserva Inicio y el destino actual, ocultando los
niveles intermedios para evitar desbordamiento. Validado: `npx.cmd tsc
--noEmit` y `npm.cmd run build` pasaron.

## Escritor Valery PRS 0.7.4 (2026-07-30)

La comparación del PRS real `3259` con el generado por BAPPS Sync
`9847 / 0000000053` confirmó dos hechos:

- `PRODUCTOS_FACTURABLES` en esta versión de Valery solo expone
  `CODIGO_BUSQUEDA`, `TIPO` y `CODIGO_PRODUCTO`; no es una fuente válida de
  nombre, unidad, impuestos ni costos.
- El renglón 15931 quedó físicamente único, pero incompleto: impuesto y bases
  fiscales en cero. Posteriormente la cabecera mostró acumulados duplicados,
  aunque los totales principales permanecieron correctos.

El agente 0.7.4 valida primero la pertenencia en `PRODUCTOS_FACTURABLES` y
después lee el maestro completo en `PRODUCTOS_TERMINADOS`. `PRODUCTOS` solo
contiene nueve campos básicos en esta instalación. Completa nombres, unidad,
tipo de precio del cliente, costos unitarios/promedio con y sin impuesto,
código fiscal, marca e historial vigente de moneda. La cabecera incorpora
costos, bases de consumo e historial monetario.

La réplica MySQL `bapps_demo.PRODUCTOS_TERMINADOS` confirmó para `111-1`:
`EXENTO_IMPUESTO=F`, `ALICUOTA_IMPUESTO=16`,
`IMPUESTO_VENTA_CODIGO=01`, moneda `02` y costos completos. El escritor toma
la tasa desde Valery y exige que coincida con la app
(`VALERY_TAX_MISMATCH`). Para compatibilidad con el Firebird legacy, reafirma
por `UPDATE` los acumulados fiscales del renglón antes de su validación y del
commit.

Antes del commit Firebird se releen cabecera y detalles y se comparan:
cantidad de renglones, cantidad de artículos, neto, impuesto y total. Una
diferencia provoca rollback con `VALERY_WRITE_VALIDATION_FAILED`; el Centro
ya presenta este código con una acción específica y nunca confirma el job.

Validaciones:

```text
99 pruebas Python del agente   PASS
npm.cmd run build              PASS
```

Instalador:

```text
agent/release/BAPPS-Sync-Setup-0.7.4.exe
SHA256 CE29ABF8B7DD7221DF442413EAF91584E5BFC3CFFE21B26E5AFA7186A6FF8B7A
```

La prueba siguiente debe crear un pedido nuevo; no reutilizar el job
completado de `COT-00005`, porque la idempotencia devolverá el PRS anterior.
Después de ejecutar, comparar el nuevo `VENTAS` y `VENTAS_DETALLES` antes de
abrirlo o editarlo en Valery.

## Próximo orden seguro

Actualización 2026-07-29 — el alta de recetas ya comienza en `Catálogo de
syncs → Nuevo sync`. El drawer crea atómicamente catálogo y versión 1
declarativa con tabla/columnas explícitas, filtro anual cerrado, destino,
estrategia, propiedad y límites. No descarga código ni acepta SQL libre. La
inspección remota de metadatos sigue siendo el siguiente incremento para
completar el flujo plug-and-play. Guía:
`docs/CREAR_SINCRONIZADOR_DESDE_CATALOGO.md`.

Actualización 2026-07-29: usar 0.6.1, no 0.6.0. La instalación remota de 0.6.0
heredó una identidad 0.5.4 sin clave pública y produjo polling de
`/agent/config` cada segundo. El hotfix fija offline la pública derivada del
`.env`, preserva token/DPAPI, aplica backoff y añade rotación planificada sin
reinstalación mediante un llavero y transiciones firmadas. Ver
`docs/ESTADO_AGENTE_0.6.1_HOTFIX.md`. La URL del laboratorio sigue en HTTP;
HTTPS es obligatorio antes de producción.

Actualización 2026-07-29 — usar 0.6.2 como versión vigente. En la prueba remota
se observó que heartbeat marcaba `Conectado`, pero `/agent/config` rechazaba la
firma y el siguiente heartbeat ocultaba temporalmente el error. La causa raíz
fue `syncs` firmado como Collection antes de que `JsonResponse` lo convirtiera
en arreglo. El Centro normaliza ahora todo `JsonSerializable` y entrega una
firma que el verificador Python acepta. El agente 0.6.2 conserva por separado
accesibilidad del Centro y validez de configuración. Detalle, pruebas e
instalador: `docs/ESTADO_AGENTE_0.6.2_FIRMA_Y_ESTADO.md`.

Actualización 2026-07-28: el candidato 0.6.0 ya está construido y validado sin
instalarlo. Artefactos, hashes, alcance y límites están en
`docs/ESTADO_AGENTE_0.6.0_CANDIDATO.md`. `AGT-VALERY-01` continúa estable en
0.5.4. El siguiente paso no es recompilar: es cerrar UI/RBAC/inspección de
recetas y luego instalar una identidad aislada `AGT-VALERY-PILOTO`.

El usuario cambió la prioridad al agente todo terreno, Profit y la fórmula de
recetas de lectura. El orden autoritativo está en
`docs/PLAN_RESILIENCIA_Y_RECETAS_LECTURA_2026-07-27.md`:

1. Congelar el contrato de receta/snapshot y propiedad de tablas.
2. Construir el harness de fallos y medir la outbox con 10.000 eventos.
3. Endurecer firma, TLS, RBAC, secretos y observabilidad.
4. Implementar el motor genérico SQL Server y el flujo de inspección del
   Centro.
5. Generar un instalador nuevo y pilotar `clientes`/`art` en una máquina
   Profit de laboratorio.

La lectura de Profit ya no se plantea como un sincronizador Python por tabla.
La especificación autoritativa es
`docs/ESPECIFICACION_MOTOR_UNICO_LECTURA_PROFIT_2026-07-27.md` y su contrato
validable es `docs/contracts/read-recipe-v1.schema.json`. Cubre los filtros del
año actual, renglones delimitados por su padre, nombres destino legacy,
constantes, la transformación fiscal de artículos y el histórico diario de
moneda, sin admitir SQL ni código remoto.

Las validaciones PHP/Pint del tooltip y la comprobación manual de toast quedan
documentadas y diferidas; no se pierden. No intervenir `AGT-VALERY-01`.

## Escritor Valery PRS 0.7.5

- Se confirmó que `Decimal('1.00')` y `Decimal('1.0')` no causaban la
  validación fallida. La discrepancia real era
  `VENTAS_DETALLES.TOTAL_IMPUESTO`: esperado `1856.77`, leído `0.00`.
- El agente intenta primero el `UPDATE` fiscal parametrizado. Si Firebird
  conserva el impuesto en cero, ejecuta dentro de la misma transacción un
  fallback calculado por Firebird: `TOTAL_IMPUESTO = TOTAL - TOTAL_NETO`.
- Se releen inmediatamente todos los campos fiscales del renglón. Si tampoco
  coinciden, se hace rollback y el error muestra el estado posterior a ambos
  intentos; no se confirma un PRS inconsistente.
- Suite completa confirmada: 101 pruebas.
- Instalador: `agent/release/BAPPS-Sync-Setup-0.7.5.exe`.
- SHA-256:
  `C219DF8B9D36EE123D501057ABDE7AD76EDCB08B5CE9710255ECDB69A8F5DF1B`.

## Compatibilidad temporal Valery PRS 0.7.6

- Por decisión explícita del usuario se permite que la instalación legacy
  conserve en cero `TOTAL_IMPUESTO`, `TOTAL_BASE_IMPONIBLE` y
  `TOTAL_IMPUESTO_FISCAL` de `VENTAS_DETALLES`.
- La excepción no desactiva la protección general: siguen validándose
  estrictamente cantidad de renglones, cantidades, netos, totales y todos los
  totales fiscales de la cabecera `VENTAS`.
- El agente todavía intenta escribir y recalcular los campos de detalle antes
  de aplicar la compatibilidad.
- Suite completa confirmada: 102 pruebas.
- Instalador: `agent/release/BAPPS-Sync-Setup-0.7.6.exe`.
- SHA-256:
  `7DFB8E0D236617B6F7C3020883CBFE3A1D8E88B2ACB14341432849020899BC43`.

## Normalización de cabecera Valery PRS 0.7.7

- Se confirmó que Valery acumula automáticamente al insertar el detalle:
  duplicaba neto de líneas, total de líneas, cantidad y número de renglones
  porque la cabecera ya llegaba cargada.
- La cabecera se crea ahora con esos acumuladores en cero.
- Tras insertar todos los detalles, el agente normaliza autoritativamente los
  totales, bases, impuestos, costos, cantidades e ítems de `VENTAS`.
- La validación final permanece antes del commit.
- Suite completa confirmada: 103 pruebas.
- Instalador: `agent/release/BAPPS-Sync-Setup-0.7.7.exe`.
- SHA-256:
  `F39B1551D0D2414DA194DA6EB241E09105C67C93727F8B7F05FB6D89859CA42F`.

## Numeración PRS Valery 0.7.8

- El documento dejó de depender del PRS con mayor `CORRELATIVO`, porque un
  borrador con `DOCUMENTO` vacío o no numérico reiniciaba la secuencia en 1.
- El agente obtiene ahora el máximo de todos los documentos PRS numéricos,
  suma uno y verifica colisiones antes de insertar.
- Los documentos vacíos, nulos o textuales se ignoran sin reiniciar la serie.
- Suite completa confirmada: 104 pruebas.
- Instalador: `agent/release/BAPPS-Sync-Setup-0.7.8.exe`.
- SHA-256:
  `FA0AEAB92E6CDA1837EC371B9CE2692AB96DF0A8EA29DFEB327B761A01195D8B`.

## Cierre de estado: escritor PRS Valery y agente 0.7.10 (2026-08-03)

Este bloque sustituye cualquier indicación anterior de instalar 0.7.2–0.7.9 para el piloto de presupuestos. El artefacto vigente es:

```text
agent/release/BAPPS-Sync-Setup-0.7.10.exe
20.752.719 bytes
SHA-256 2223C91B9E827088C458B5FB6341D13900852899D0B98750BC621D0A16E36715
```

### Lo realizado

- Se implementó `valery_prs_writer_v1`: reclama un pedido desde la API privada, usa lease, idempotencia por `ORDEN_DE_COMPRA`, reintentos de colisiones y confirma el job sólo después del commit Firebird.
- Escribe presupuestos `PRS`, no facturas, pedidos ni inventario. El plazo es fijo: fecha original del pedido + 15 días.
- Calcula con `Decimal` y redondeo comercial; valida cliente, vendedor, productos, impuestos, factor de moneda y esquema. El encabezado queda en moneda `01`, los renglones en moneda `02` con la tasa vigente.
- Inserta `VENTAS`, `VENTAS_AD`, `VENTAS_ESTADOS`, `VENTAS_EXT`, `VENTAS_DETALLES` y textos en `VENTAS_DETALLES_EXT` en una única transacción. La adición de las tres tablas auxiliares corrige la diferencia encontrada entre los PRS nativos visibles y los creados inicialmente por el agente.
- Se normalizan acumulados de `VENTAS` tras insertar renglones para impedir duplicaciones de la lógica interna de Valery.
- Compatibilidad temporal aprobada: si la base legacy fuerza a cero campos fiscales derivados del detalle, no se cancela sólo por ese hecho. Se mantienen estrictos renglones, cantidades, neto, total y cabecera. Debe revisarse antes de producción.
- Se reparó el empaquetado: 0.7.9 excluía `tkinter`/Tcl/Tk y fallaba al abrir el panel. 0.7.10 incorpora estas dependencias y ejecuta una autoprueba del binario portable que inicializa Tcl antes de publicar el Setup.

### Evidencia de validación

```text
Pruebas Python del agente: 106/106 PASS
Autoprueba del ejecutable portable 0.7.10: PASS
```

No es aceptación final de Valery: el último Setup todavía debe comprobarse dentro del Administrador de Documentos. Los correlativos de prueba antiguos `9855` y `9856` quedaron en estados parciales y no sirven para evaluar 0.7.10.

### Próximo paso obligatorio

1. Instalar 0.7.10 en la máquina de Valery sobre la instalación actual.
2. Abrir el panel del agente para confirmar que inicia.
3. Crear un pedido nuevo y ejecutar `prs_valery`; no reutilizar un job anterior.
4. Confirmar el job en la app, el nuevo `VENTAS` y sus filas auxiliares, y que aparece en el Administrador de Documentos de Valery.
5. Si aparece, comparar renglones y totales contra un PRS nativo antes de habilitar escritura fuera del piloto.

La referencia de detalle es `docs/VALERY_PRS_WRITER_V1.md`.

## Instrucción para iniciar otro chat

```text
Trabaja en C:\Sync\Valery\bapps-sync. Lee primero
docs/HANDOFF_CONTINUACION_2026-07-27.md, docs/ONGOING.txt y
docs/ARQUITECTURA_SINCRONIZADORES_Y_DATOS.md y
docs/PLAN_RESILIENCIA_Y_RECETAS_LECTURA_2026-07-27.md y
docs/ESPECIFICACION_MOTOR_UNICO_LECTURA_PROFIT_2026-07-27.md y
docs/VALERY_PRS_WRITER_V1.md. La central usa MySQL bapps_sync; no confundas esa
base con la fuente del cliente ni con el MySQL destino dedicado a réplicas.
Para el piloto actual de escritura, el siguiente paso autorizado es instalar
0.7.10 en la PC Valery y ejecutar un pedido nuevo; no modifiques los
correlativos de prueba anteriores. No descargues código de sincronizadores
desde el Centro.
```
