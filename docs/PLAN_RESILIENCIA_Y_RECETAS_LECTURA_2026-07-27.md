# Plan autoritativo: resiliencia y recetas de lectura

Fecha: 2026-07-27

Este documento define el siguiente bloque de BAPPS Sync. Complementa el plan
maestro y sustituye cualquier interpretación anterior según la cual el Centro
descargaría código Python hacia los agentes. El contrato funcional detallado
del motor único y el inventario legacy están en
`docs/ESPECIFICACION_MOTOR_UNICO_LECTURA_PROFIT_2026-07-27.md`.

## Objetivo

Convertir el agente en una instalación reutilizable para Profit, Valery y
otros sistemas administrativos:

1. El instalador incorpora los motores de lectura confiables.
2. En la máquina del cliente se configura un origen y un MySQL destino.
3. Desde el Centro se indica la tabla, se inspecciona su estructura y se
   seleccionan las columnas.
4. El Centro entrega una receta declarativa, no código.
5. El agente replica una fotografía completa del conjunto definido por la
   receta en una tabla administrada por BAPPS Sync. El destino es configurable
   para preservar consumidores legacy, aunque por defecto use el nombre origen.

Profit/SQL Server es el primer piloto. Firebird Valery debe usar después la
misma fórmula sin modificar `AGT-VALERY-01` 0.5.4 hasta superar todos los gates.

## Dos familias distintas

### Recetas configurables de lectura

El instalador contiene un `TableSnapshotSynchronizer` y conectores aprobados
para SQL Server, Firebird y, posteriormente, MySQL. La asignación desde la web
solo descarga:

- tabla de origen;
- columnas seleccionadas;
- tabla de destino;
- estrategia `full_snapshot`;
- filtros estructurados y alcance opcional por tabla padre;
- constantes y nombres de transformaciones empaquetadas permitidas;
- tamaño de lote, timeout y versión de receta;
- fingerprint de esquema y firma.

No se descarga ni ejecuta Python, DLL, SQL libre o expresiones suministradas
desde la web.

### Sincronizadores empaquetados con lógica de negocio

Pedidos de escritura, joins arbitrarios, cálculos no previstos y reglas
específicas son módulos confiables desarrollados manualmente, probados y distribuidos
dentro de una nueva versión firmada del instalador. El Centro puede
asignarlos y configurarlos, pero no inventar ni descargar su implementación.

Ejemplo: el legacy de artículos consulta `tab_enc` y calcula información
tributaria. El motor genérico invoca la transformación confiable
`profit.article_tax_rate_v1`, incluida en el instalador y nombrada por la
receta. La web no define ni descarga su código.

## Resultado de la revisión del legacy Profit

Los ejemplos están en
`docs/backend-design/BAPPS_Sync_Development_Pack_v1.1/Sync_Lectura_Legacy_Profit_Coloreal`.

| Origen | Destino legacy | Estrategia encontrada | Particularidad |
|---|---|---|---|
| `art` | `articulos_sync` | reemplazo total | enriquecimiento con `tab_enc` |
| `factura` | `factura_sync` | reemplazo total | solo año actual |
| `reng_fac` | `reng_fac_sync` | reemplazo total | filas de facturas del año actual |
| `pedidos` | `pedidos_sync` | reemplazo total | solo año actual |
| `reng_ped` | `reng_ped_sync` | reemplazo total | filas de pedidos del año actual |
| `not_ent` | `not_ent_sync` | reemplazo total | solo año actual |
| `reng_nde` | `reng_nde_sync` | reemplazo total | filas de notas del año actual |
| `docum_cc` | `docum_cc_sync` | existen variantes total e incremental | revisar consumidor antes de migrar |
| `clientes` | `cliente_sync` | inserción/actualización | clave `co_cli` |
| `cat_art` | `cat_art_sync` | inserción | usa `rowguid`/flag legacy |
| `lin_art` | `lin_art_sync` | inserción | usa `rowguid`/flag legacy |
| `sub_lin` | `sub_lin_sync` | inserción | usa `rowguid`/flag legacy |
| `vendedor` | `vendedor_sync` | inserción | usa `rowguid`/flag legacy |
| `condicio` | `condicio_sync` | inserción | usa `rowguid`/flag legacy |
| `bancos` | `bancos_sync` | inserción/actualización | usa `rowguid` |
| `cuentas` | `cuentas_sync` | inserción/actualización | usa `rowguid` |
| `moneda` | `moneda_sync` | histórico diario | solo `US$`, clave `(co_mone,date)` |

La nueva fórmula normaliza las tablas de estado a fotografía completa. Conserva
dos excepciones controladas dentro del mismo motor: la transformación fiscal
de `art` y `daily_history_v1` para `moneda`. Los filtros anuales y las
relaciones padre/renglón son datos declarativos compilados de forma segura, no
SQL libre. Los sincronizadores legacy se conservan como referencia y oráculo
de comparación, no como código que el agente ejecutará.

## Semántica de fotografía completa

No se ejecutará `TRUNCATE` sobre la tabla activa. MySQL documenta que
`TRUNCATE TABLE` hace commit implícito y no puede revertirse con `ROLLBACK`.

Algoritmo:

1. Validar receta, firma, conexión, permisos, versión de MySQL y espacio
   operativo.
2. Confirmar que la tabla activa es propiedad de BAPPS Sync. Una tabla
   preexistente sin marcador de propiedad produce `TARGET_TABLE_NOT_MANAGED`.
3. Crear una tabla sombra con nombre interno, esquema nuevo e InnoDB.
4. Abrir una transacción consistente y de solo lectura en el origen.
5. Leer toda la tabla en lotes y escribir exclusivamente en la sombra.
6. Cerrar la fotografía del origen.
7. Validar esquema, número de filas, nulabilidad, conversiones, inserciones y
   unicidad cuando exista una clave.
8. Intercambiar en una sola operación la sombra y la tabla activa.
9. Conservar una copia anterior administrada para rollback.
10. Limpiar sombras/respaldos antiguos solo si sus marcadores prueban que
    pertenecen a BAPPS Sync.

Si falla la fuente, la red, MySQL, una conversión, una validación, el disco o
la cancelación antes del intercambio, la tabla activa permanece intacta.

El reemplazo refleja inserciones, modificaciones y eliminaciones existentes
en la fotografía del origen. No requiere una clave única para funcionar,
aunque una clave mejora paginación, diagnósticos y validación.

La operación `RENAME TABLE` de múltiples tablas es atómica y requiere
`ALTER`/`DROP` sobre los nombres originales y `CREATE`/`INSERT` sobre los
nuevos. Referencias oficiales:

- https://dev.mysql.com/doc/refman/8.0/en/rename-table.html
- https://dev.mysql.com/doc/refman/8.0/en/truncate-table.html
- https://dev.mysql.com/doc/refman/8.0/en/atomic-ddl.html

## Consistencia por motor

- SQL Server Profit: transacción `SNAPSHOT` de solo lectura. El preflight debe
  comprobar que la base permite snapshot isolation. No se habilita ni modifica
  automáticamente desde el agente.
- Firebird: transacción read-only con aislamiento snapshot.
- MySQL como origen futuro: `REPEATABLE READ` con consistent snapshot.

No se usará `NOLOCK`, porque puede leer filas sucias, duplicadas u omitidas.
Si el motor no ofrece la fotografía consistente requerida, la ejecución falla
antes del intercambio y explica el requisito pendiente.

## Propiedad y seguridad del MySQL destino

La base configurada como destino debe dedicarse a réplicas administradas por
BAPPS Sync. Esto es necesario porque MySQL no permite conceder DDL dinámico
seguro por patrón de nombres dentro de una base operacional.

Reglas:

- la tabla visible usa un nombre validado configurado en la receta; para
  instalaciones nuevas el valor predeterminado es el nombre origen;
- una tabla de otro dueño nunca se adopta ni sobrescribe;
- una tabla de metadatos protegida registra receta, versión, fingerprint,
  tabla activa, respaldo y último intercambio;
- las tablas internas usan nombres no configurables y un identificador de
  ejecución generado por el agente;
- solo se aceptan identificadores validados y citados por el conector;
- valores siempre parametrizados;
- el usuario de origen es de solo lectura;
- el usuario MySQL se limita a la base dedicada y recibe únicamente los
  permisos necesarios para crear, cargar, validar, renombrar y retirar tablas
  administradas;
- las credenciales se guardan localmente con DPAPI de máquina y nunca se
  incluyen en recetas, previews, outbox, logs o auditoría.

MySQL 8.0+ e InnoDB son requisitos del modo transaccional v1.

## Evolución y rollback de esquema

Cada cambio de columnas crea una versión inmutable de receta:

1. `draft`;
2. inspección y preview;
3. validación en el agente;
4. publicación firmada;
5. asignación a un agente;
6. construcción completa de una sombra con el nuevo esquema;
7. intercambio atómico;
8. conservación de una versión anterior.

No se altera columna por columna la tabla activa. Agregar, retirar o cambiar
un tipo seleccionado construye una nueva tabla. Rollback vuelve a intercambiar
la copia anterior si conserva el marcador, receta y fingerprint esperados.

## Inspección desde el Centro

El MVP permite introducir manualmente el nombre de la tabla. Listar todas las
tablas queda como mejora posterior.

El agente devuelve metadatos y una página de datos:

- columnas, tipos, tamaño, nulabilidad, PK e índices únicos;
- máximo 100 filas por página y un máximo estricto de bytes;
- cursor por clave cuando exista; fallback acotado por offset cuando no;
- valores binarios y columnas con patrón de secreto se enmascaran;
- sin exportación completa.

Solo `admin` puede inspeccionar datos, crear, validar, publicar o revertir
recetas. `operator` puede asignar, ejecutar, pausar y revisar resultados.
Cada acceso queda auditado. Las páginas se cifran temporalmente en el Centro,
expiran en diez minutos y nunca se copian a auditoría.

## Firma, identidad y transporte

- HTTPS con validación de certificado es obligatorio antes del piloto.
- El bootstrap fija la clave pública de firma del Centro.
- Laravel firma el JSON canónico de receta/configuración; la clave privada no
  se guarda en la base central.
- El agente verifica firma, hash, agente destinatario, versión mínima y
  monotonía de versión antes de activar una receta.
- Un rollback exige una instrucción firmada explícita.
- Tokens de enrolamiento son de un solo uso; tokens operativos pueden
  rotarse/revocarse y permanecen protegidos con DPAPI.
- Login del panel incorpora rate limiting, expiración/revocación y RBAC real.

## Observabilidad

Heartbeat y panel deben distinguir:

- `healthy`;
- `degraded`;
- `backpressure`;
- `blocked`.

El diagnóstico incluye, sin secretos:

- motivo y código seguro;
- estado de fuente y destino;
- versión/fingerprint de receta;
- fase `inspect`, `extract`, `load`, `validate` o `swap`;
- filas leídas/cargadas;
- tabla sombra pendiente;
- outbox por cantidad/bytes y evento más antiguo;
- espacio libre local;
- último intento, próximo retry y `Retry-After`;
- versión del agente, drivers y resultado del preflight.

## Matriz de resiliencia obligatoria

Las pruebas se ejecutan primero en laboratorio, nunca sobre
`AGT-VALERY-01` sin autorización y ventana.

1. MySQL BAPPS inaccesible antes de comenzar: no abrir el origen.
2. Timeout/caída MySQL durante carga: tabla activa intacta.
3. Caída después de cargar y antes del swap: tabla activa intacta y sombra
   recuperable/limpiable.
4. Reinicio durante el swap: una única versión visible y metadatos coherentes.
5. Disco local lleno y permisos de outbox denegados: bloquear ejecuciones
   nuevas si no puede persistirse `run_started`.
6. Disco MySQL lleno durante sombra: tabla activa intacta.
7. DNS, TLS inválido, red intermitente, HTTP 429 y 5xx: retry con backoff,
   jitter y respeto de `Retry-After`, sin deshabilitar TLS.
8. Outbox de 10.000 eventos: cero pérdida/corrupción, heartbeat y comandos
   siguen respondiendo, drenaje acotado y deduplicación central.
9. Esquema cambiado en origen: bloquear receta por fingerprint.
10. Tabla destino ajena o marcador manipulado: bloquear sin DDL.
11. Credenciales insuficientes: preflight falla con permiso exacto faltante.
12. Usuario `operator` intentando preview/publicación: 403 y auditoría.

La outbox de archivos vigente se somete primero al benchmark de 10.000
eventos. Si no mantiene memoria acotada, control loop responsivo y drenaje por
lotes, se migra idempotentemente a SQLite local; no se cambia por anticipación
sin medir.

## Correctitud

- normalización explícita de `CHAR`, Unicode, charset Firebird, bytes,
  `NULL`, booleanos, enteros, `DECIMAL`, moneda, fecha, hora y zona;
- prohibido convertir `DECIMAL` a `float`;
- límites por fila, celda, columnas y duración;
- conteo origen/sombra obligatorio;
- digest incremental de los valores normalizados durante extracción/carga;
- commit por lote solo en la sombra;
- checkpoints de fase, no de reemplazo parcial;
- idempotencia por `run_id`, receta y nombre de sombra;
- reintentar nunca toca la tabla activa hasta completar una nueva fotografía.

## Instalador y plug-and-play

El instalador incluye:

- runtime, servicio Windows y GUI;
- `TableSnapshotSynchronizer`;
- conectores SQL Server y Firebird con sus librerías aprobadas;
- registro cerrado de módulos empaquetados;
- preflight de ODBC/Firebird, TLS, origen, MySQL, permisos y directorios;
- actualización y rollback del agente.

Después de instalar solo se configuran bootstrap, origen y MySQL destino. La
asignación web descarga una receta/configuración. Si una receta requiere un
módulo empaquetado no presente, el Centro exige una versión nueva del agente;
jamás descarga el módulo como código.

## Orden de ejecución

1. Congelar contratos de receta, propiedad y snapshot.
2. Construir el harness de fallos y ejecutar la línea base de outbox 10.000.
3. Endurecer transporte, firma, roles, secretos y observabilidad.
4. Implementar el motor de sombra/swap y el adaptador SQL Server.
5. Implementar inspección/preview y versionado de recetas en Centro.
6. Generar un instalador nuevo para una máquina Profit de laboratorio.
7. Piloto con `clientes` directo en una base MySQL dedicada.
8. Piloto con `art` y `profit.article_tax_rate_v1`; comparar también el cálculo
   legacy de `tab_enc`.
9. Ejecutar toda la matriz de resiliencia.
10. Incorporar el adaptador Firebird a la misma fórmula y validarlo fuera de
    la instalación Valery estable.
11. Diseñar por separado el primer sincronizador empaquetado de escritura
    (pedidos), con permisos, idempotencia y reglas propias.

## Fuera del primer bloque

- SQL libre;
- código remoto;
- joins arbitrarios, expresiones y columnas calculadas libres; se permite un
  `parent_scope` seguro y transformaciones empaquetadas nombradas;
- múltiples orígenes/destinos por agente;
- adopción automática de tablas existentes; la migración legacy usa un flujo
  administrativo explícito, respaldado y auditado;
- escritura hacia Profit;
- listado automático de tablas;
- actualización de `AGT-VALERY-01`.
