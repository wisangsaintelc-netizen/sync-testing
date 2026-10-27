# Especificación autoritativa: motor único de lectura Profit

Fecha: 2026-07-27

## Decisión

Todos los `sync_*` de lectura ubicados en
`docs/backend-design/BAPPS_Sync_Development_Pack_v1.1/Sync_Lectura_Legacy_Profit_Coloreal`
serán sustituidos por **un solo motor de lectura incluido en el agente**.

El Centro BAPPS Sync no descargará Python, ejecutables, DLL ni SQL libre. El
Centro crea, versiona, firma y asigna recetas declarativas. El agente valida la
firma, guarda la última versión válida y ejecuta la receta con los conectores y
operadores seguros que ya vienen en el instalador.

Esto permite configurar desde la web:

- conexión lógica de origen, sin exponer sus credenciales;
- esquema y tabla de Profit;
- columnas que se copiarán;
- filtros permitidos;
- alcance por tabla padre para renglones;
- nombre de la tabla MySQL destino;
- frecuencia y límites;
- estrategia de publicación;
- transformaciones confiables incluidas en el agente.

## Frontera KISS

Hay una sola implementación `DeclarativeTableReader`. La variación entre
sincronizadores es JSON validado.

El agente contiene:

- adaptadores SQL Server y Firebird;
- introspección de esquemas;
- compilador seguro de recetas a consultas parametrizadas;
- lector por lotes;
- normalización de tipos;
- carga a tabla sombra;
- validación y swap atómico;
- estrategias y transformaciones nombradas en un registro cerrado.

El Centro contiene:

- catálogo agrupado por base de datos, sistema administrativo y versión;
- constructor de recetas;
- preview enmascarado;
- versiones inmutables;
- firma y asignación;
- auditoría y RBAC.

Las credenciales de SQL Server/Firebird/MySQL solo viven en la máquina del
cliente, protegidas con DPAPI de máquina. Una receta usa referencias locales
como `profit_principal` y `bapps_mysql`; nunca contiene contraseñas.

## Lo observado en los sincronizadores legacy

| Origen Profit | Destino legacy | Columnas | Alcance o particularidad |
|---|---|---|---|
| `art` | `articulos_sync` | lista explícita | fotografía completa; consulta la última fila de `tab_enc` y transforma `tipo_imp` |
| `clientes` | `cliente_sync` | lista explícita | legacy hace upsert por `co_cli`; el estándar nuevo hará fotografía completa |
| `cat_art` | `cat_art_sync` | lista explícita | legacy solo inserta y agrega `sync=1`; el estándar nuevo hará fotografía completa |
| `lin_art` | `lin_art_sync` | lista explícita | legacy solo inserta y agrega `sync=1`; el estándar nuevo hará fotografía completa |
| `sub_lin` | `sub_lin_sync` | lista explícita | legacy solo inserta y agrega `sync=1`; el estándar nuevo hará fotografía completa |
| `vendedor` | `vendedor_sync` | lista explícita | legacy solo inserta y agrega `sync=1`; el estándar nuevo hará fotografía completa |
| `condicio` | `condicio_sync` | lista explícita | legacy solo inserta y agrega `sync=1`; el estándar nuevo hará fotografía completa |
| `factura` | `factura_sync` | todas, descubiertas | `fec_emis` del año calendario actual |
| `reng_fac` | `reng_fac_sync` | todas, descubiertas | solo filas cuyo padre `factura.fact_num` pertenece al año actual |
| `pedidos` | `pedidos_sync` | todas, descubiertas | `fec_emis` del año calendario actual |
| `reng_ped` | `reng_ped_sync` | todas, descubiertas | solo filas cuyo padre `pedidos.fact_num` pertenece al año actual |
| `not_ent` | `not_ent_sync` | todas, descubiertas | `fec_emis` del año calendario actual |
| `reng_nde` | `reng_nde_sync` | todas, descubiertas | solo filas cuyo padre `not_ent.fact_num` pertenece al año actual |
| `docum_cc` | `docum_cc_sync` | lista explícita | tipos de documento permitidos; hay dos variantes legacy |
| `bancos` | `bancos_sync` | lista explícita | legacy hace upsert por `co_ban`; el estándar nuevo hará fotografía completa |
| `cuentas` | `cuentas_sync` | lista explícita | legacy hace upsert por `cod_cta`; el estándar nuevo hará fotografía completa |
| `moneda` | `moneda_sync` | `co_mone`, `mone_des`, `cambio` | solo `US$`; conserva una cotización por día |

La carpeta principal ejecuta maestros en este orden: categorías, líneas,
sublíneas, artículos, clientes, vendedores y condiciones. Facturas, pedidos,
notas de entrega, documentos de cuentas por cobrar y pagos tienen maestros
separados.

### Dos excepciones reales

1. **Artículos:** no es una copia directa. El legacy lee la tasa más reciente
   de `dbo.tab_enc` y convierte códigos de `tipo_imp` en tasas. El motor único
   invocará la transformación empaquetada
   `profit.article_tax_rate_v1`. La receta solo puede nombrarla; no define una
   expresión.
2. **Moneda:** no representa el estado completo de `moneda`; construye un
   histórico diario de `US$`. Usará la estrategia empaquetada
   `daily_history_v1`, con clave `(co_mone, date)`. No debe fingirse que es un
   `full_snapshot`.

`docum_cc` contiene una discrepancia: una variante filtra `N/DB` y otra `DB`.
La receta piloto no debe publicarse hasta inspeccionar los valores reales de la
base Profit y confirmar cuál consume el sistema actual. Esa decisión quedará
auditada en la versión publicada.

## Contrato de receta v1

El contrato completo y validable está en
`docs/contracts/read-recipe-v1.schema.json`.

Ejemplo resumido para facturas:

```json
{
  "schema_version": "1.0",
  "recipe_code": "profit_factura_current_year",
  "recipe_version": 1,
  "engine": "declarative_table_reader",
  "minimum_agent_version": "0.6.0",
  "source": {
    "profile_ref": "profit_principal",
    "driver": "sqlserver",
    "schema": "dbo",
    "table": "factura",
    "columns": ["fact_num", "fec_emis", "co_cli"]
  },
  "scope": {
    "where": {
      "operator": "date_window",
      "column": "fec_emis",
      "window": "current_calendar_year"
    }
  },
  "target": {
    "profile_ref": "bapps_mysql",
    "table": "factura_sync",
    "strategy": "full_snapshot",
    "ownership": "managed_only"
  },
  "limits": {
    "batch_rows": 1000,
    "statement_timeout_seconds": 60,
    "max_runtime_seconds": 1800
  }
}
```

### Columnas

Durante la inspección el operador puede pulsar “seleccionar todas”, pero al
publicar se guarda la lista explícita y el fingerprint del esquema. No se
publica `SELECT *`. Si Profit agrega, elimina o cambia una columna, el agente
bloquea la receta con `SOURCE_SCHEMA_MISMATCH`; un administrador revisa y
publica una versión nueva.

La asignación puede agregar columnas constantes de una lista controlada, por
ejemplo `sync=1` para compatibilidad. Una constante no acepta expresiones.

### Filtros permitidos

La receta no contiene fragmentos SQL. El compilador admite únicamente:

- `eq`, `in`, `is_null`, `is_not_null`;
- `and` y `or` con profundidad y cantidad máximas;
- `date_window` con ventanas nombradas, comenzando por
  `current_calendar_year`;
- parámetros escalares tipados y limitados.

Tabla, esquema y columnas deben existir en la introspección firmada. El
adaptador cita identificadores; todos los valores se parametrizan.

### Alcance por tabla padre

Los renglones no necesitan SQL configurable. Se admite un único `parent_scope`
estructurado que el adaptador compila como `EXISTS`:

```json
{
  "parent_scope": {
    "schema": "dbo",
    "table": "factura",
    "child_column": "fact_num",
    "parent_column": "fact_num",
    "where": {
      "operator": "date_window",
      "column": "fec_emis",
      "window": "current_calendar_year"
    }
  }
}
```

`EXISTS` evita multiplicar renglones si el padre no fuera único. V1 permite un
solo padre y no expone joins arbitrarios. La relación, columnas y filtro se
validan contra metadatos antes de ejecutar.

### Nombre de destino

El nombre destino es configurable porque los consumidores actuales pueden
depender de nombres como `articulos_sync`. El valor predeterminado para
instalaciones nuevas será el nombre de la tabla origen; las recetas de
migración pueden conservar el nombre legacy.

Una tabla preexistente nunca se adopta silenciosamente. Hay dos caminos:

- `create_new`: falla si el nombre existe;
- `managed_only`: permite reemplazar solo si el registro local de propiedad y
  la tabla de metadatos MySQL prueban que BAPPS Sync la creó.

La adopción inicial de una tabla legacy es una operación administrativa
separada: preflight, comparación de esquema, respaldo con nombre inmutable,
confirmación explícita, marcador de propiedad y auditoría. Nunca forma parte de
una ejecución programada.

## Fotografía transaccional

“Traer la tabla completa” no significa vaciar la tabla activa. Cada ejecución:

1. valida firma, versión, esquema, propiedad, permisos y espacio;
2. abre una transacción de solo lectura con aislamiento `SNAPSHOT` en SQL
   Server;
3. crea una tabla sombra InnoDB;
4. lee el conjunto completo definido por la receta en lotes;
5. normaliza y carga únicamente la sombra;
6. compara conteos, digest, nulabilidad y límites;
7. cierra la lectura consistente;
8. intercambia sombra y activa con un `RENAME TABLE` múltiple atómico;
9. conserva una versión anterior para rollback.

Si Profit cambia mientras se lee, la transacción conserva el mismo punto de
vista. Si hay timeout, reinicio, conversión inválida, MySQL sin espacio o
cancelación antes del swap, la tabla activa permanece intacta.

El preflight comprobará `ALLOW_SNAPSHOT_ISOLATION`; el agente no altera esa
opción en la base Profit. No se permite `NOLOCK`.

## Almacenamiento central y local

### Centro

Se incorporarán entidades separadas:

- `sync_recipes`: identidad, clasificación y estado;
- `sync_recipe_versions`: JSON canónico inmutable, hash, firma, autor y fecha;
- `agent_syncs`: receta/version asignada, estado, frecuencia y último acuse;
- `recipe_inspections`: metadatos temporales, enmascarados y con expiración;
- auditoría de inspección, publicación, asignación, rollback y adopción.

No se debe sobrecargar indefinidamente `agent_syncs.config_json`: conservará
la proyección compacta necesaria para compatibilidad mientras la versión
autoritativa vive en `sync_recipe_versions`.

### Agente

El agente guarda atómicamente:

- receta firmada activa;
- última receta válida;
- hash y versión aceptada;
- acuse de activación;
- referencias a perfiles locales;
- journal de sombra/swap para recuperación.

Las credenciales quedan en almacenes locales DPAPI separados. Si el Centro no
está disponible, el agente puede seguir ejecutando la última receta válida. Una
configuración nueva inválida nunca reemplaza la última válida.

## Encaje con el código actual

La base existente permite evolucionar sin rehacer el agente:

- `AgentSync` ya dispone de `config_version` y `config_json`;
- `AgentConfigController` ya proyecta `syncs[].config` hacia el agente;
- `AgentService` ya descarga configuración y continúa programando con la copia
  local cuando el Centro no responde;
- `ConfigStore` ya escribe `active-config.json` y
  `active-config.last-valid.json` atómicamente y protege la contraseña MySQL
  con DPAPI;
- `SyncRunner` ya concentra ejecución, cancelación, resultado y outbox;
- `SynchronizerRegistry` ya es la única puerta de resolución.

Los cambios mínimos y explícitos serán:

1. introducir versiones inmutables de receta en Laravel y proyectar la versión
   publicada dentro de `syncs[].config`;
2. firmar la configuración canónica antes de responder al agente;
3. validar firma, destinatario, versión y compatibilidad **antes** de
   `ConfigStore.save_active_config`; hoy la descarga se guarda directamente;
4. convertir `SourceConfigStore`, que hoy guarda un único origen y solo acepta
   `firebird/mysql`, en perfiles locales nombrados y agregar `sqlserver`;
5. hacer que `SynchronizerRegistry.resolve()` resuelva recetas con
   `engine=declarative_table_reader` al motor único, conservando el registro
   exacto para módulos empaquetados;
6. entregar al sincronizador la receta activa correspondiente; hoy el protocolo
   solo recibe `SyncContext`;
7. añadir journal de snapshot/swap, preflight y métricas sin alterar el contrato
   de outbox existente;
8. mantener `agent_syncs.config_json` como proyección, no como editor libre ni
   fuente histórica de versiones.

El endpoint actual no firma la configuración. Esa brecha debe cerrarse antes
del piloto Profit; HTTPS protege el transporte, pero por sí solo no ofrece la
verificación local, antirretroceso y rollback firmado exigidos.

### Avance de implementación (2026-07-27)

Ya existe en código, sin desplegar todavía en agentes productivos:

- `SourceConfigStore` admite perfiles locales DPAPI y el driver `sqlserver`;
- la GUI permite configurar SQL Server con puerto 1433 por defecto y la prueba
  exige ODBC Driver 18 con TLS validado;
- `ReadRecipe` valida columnas explícitas, filtros, alcance padre, estrategias,
  constantes y nombres de transformaciones sin permitir SQL libre;
- `DeclarativeTableReaderSynchronizer` abre destino antes que Profit, inicia
  `SNAPSHOT`, carga una sombra InnoDB y publica con `RENAME TABLE`;
- `SnapshotTablePublisher` no adopta destinos externos, conserva respaldo y
  elimina solo su sombra si la extracción falla;
- el registro resuelve una receta declarativa al motor único sin crear un
  archivo Python por tabla;
- el Centro firma la configuración completa con Ed25519 cuando se configura
  `BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY`; la clave pública queda fijada al
  enrolar y el agente rechaza recetas sin firma o alteradas.

Antes de enrolar el agente Profit debe configurarse la clave privada en el
Centro. Un agente enrolado antes de activar esa clave debe reenrolarse para
recibir la clave pública. `AGT-VALERY-01` no se modifica ni se reenrola.

Pendiente del siguiente bloque: modelos/versiones de receta y constructor web
para que un administrador publique y asigne el JSON sin editar la base; además
de journal de recuperación, preflight de ODBC/permisos y la matriz completa de
resiliencia.

## Seguridad obligatoria

- HTTPS con certificado válido; nunca `verify=false`.
- Firma Ed25519 del JSON canónico y clave pública fijada durante bootstrap.
- Firma ligada al agente, receta, versión y expiración.
- Protección contra downgrade; rollback solo mediante orden firmada.
- Token de enrolamiento de un uso y tokens operativos rotables/revocables.
- RBAC real: `admin` inspecciona/publica/adopta; `operator` asigna,
  pausa/ejecuta y consulta.
- Rate limit y auditoría para login, preview, publicación y adopción.
- Usuario SQL Server exclusivamente de lectura.
- Usuario MySQL limitado a una base dedicada a réplicas BAPPS Sync.
- Identificadores provenientes solo de introspección validada.
- Valores parametrizados, límites de filas/bytes/tiempo y previews enmascarados.
- Ningún secreto en receta, outbox, logs, errores, preview o auditoría.
- El registro de estrategias/transformaciones es cerrado y versionado dentro
  del instalador.

## Flujo de la web

La navegación del catálogo conserva la clasificación ya solicitada:

```text
Base de datos → Sistema administrativo → Versión → Sincronizador/receta
```

Flujo de creación:

1. elegir familia compatible, por ejemplo SQL Server / Profit / versión;
2. elegir un agente de laboratorio y un perfil local disponible;
3. inspeccionar esquema y escribir/seleccionar tabla;
4. seleccionar columnas;
5. configurar filtro seguro y, si aplica, alcance por padre;
6. elegir nombre destino y estrategia permitida;
7. ejecutar preview enmascarado;
8. validar receta en el agente sin publicar;
9. publicar una versión inmutable y firmada;
10. asignar y esperar acuse de descarga/activación.

El panel mostrará versión deseada, versión activa, fingerprint, última
descarga, último éxito, fase actual, filas, backlog, espacio y motivo
`degraded/blocked`.

## Migración de los legacy

1. Convertir cada `sync_*` en una receta semilla; no copiar su estructura de
   procesos, logs ni manejo de red.
2. Ejecutar legacy y motor nuevo contra el mismo snapshot de laboratorio.
3. Comparar columnas seleccionadas, conteos y digest normalizado.
4. Resolver `docum_cc`, verificar la transformación fiscal de `art` y validar
   el histórico de `moneda`.
5. Crear las nuevas tablas en una base MySQL dedicada o realizar la adopción
   explícita y respaldada de nombres legacy.
6. Cambiar consumidores solo después de aceptación.
7. Retirar ejecutables legacy cuando todas las recetas superen correctitud,
   resiliencia y rollback.

La migración no tocará `AGT-VALERY-01` 0.5.4. El primer despliegue será un
agente nuevo en una máquina Profit de laboratorio.

## Criterios de aceptación

- un solo motor ejecuta todas las recetas de lectura;
- ninguna receta contiene código o SQL libre;
- todos los campos, filtros y destinos legacy quedan representados;
- `art` y `moneda` conservan su semántica mediante capacidades empaquetadas;
- los renglones respetan el alcance temporal de sus padres;
- una ejecución fallida nunca deja una tabla visible parcial o vacía;
- el agente funciona con su última receta válida si el Centro está caído;
- origen y destino se configuran una vez en la máquina;
- asignar desde la web descarga y activa la receta sin instalar otro `.exe`;
- outbox de 10.000 eventos, disco/permisos, MySQL caído, DNS/TLS/429,
  reinicio y RBAC pasan la matriz de resiliencia;
- cada acción sensible y cambio de versión queda auditado.
