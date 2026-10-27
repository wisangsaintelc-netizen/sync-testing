# Crear un sincronizador desde Catálogo de syncs

Fecha: 2026-07-29

El flujo vive en **Catálogo de syncs → Nuevo sync**. La creación registra el
catálogo y publica la versión 1 de su receta declarativa en una sola
transacción. Si la receta no valida, no queda una tarjeta incompleta.

## Paso 1 — Identidad

- **Nombre legible:** nombre para operadores.
- **Código técnico:** identificador inmutable, en minúsculas y con guiones
  bajos.
- **Fuente:** base de datos, sistema administrativo y versión ya registrados.
- **Versión mínima del agente:** para crear e inspeccionar desde el panel,
  `0.6.4`.
- **Frecuencia:** intervalo predeterminado al asignarlo.
- **Clave funcional:** campo que identifica funcionalmente el registro.
- **Descripción:** propósito y procedencia.

## Paso 2 — Lectura y destino

- **Agente online para inspección:** máquina que tiene acceso real a la base
  origen y una versión mínima `0.6.4`.
- **Perfil local:** nombre del perfil configurado en la PC del agente;
  normalmente `default`.
- **Motor:** se deriva de la fuente; solo `firebird` o `sqlserver`.
- **Esquema:** obligatorio para SQL Server y omitido para Firebird.
- **Tabla origen:** identificador exacto de la tabla.
- **Columnas:** una por línea o separadas por coma. No se admite `SELECT`,
  cláusulas ni SQL libre.
- **Filtro anual:** opcional; genera únicamente la condición parametrizada del
  año calendario actual sobre la columna indicada.
- **Tabla destino:** tabla que BAPPS Sync administrará en el MySQL configurado
  para el agente.
- **Estrategia:** fotografía completa con reemplazo o histórico diario.
- **Propiedad:** crear una tabla nueva administrada o exigir que ya tenga el
  marcador de propiedad de BAPPS Sync.
- **Límites:** lote, timeout y duración máxima con rangos cerrados.

### Inspección centralizada de la tabla

1. Seleccionar un agente online compatible.
2. Indicar el perfil local y el identificador exacto de la tabla.
3. Pulsar **Consultar tabla**.
4. El Centro encola un comando con vigencia de cinco minutos. El agente usa
   las credenciales DPAPI de su perfil local y construye internamente una
   consulta de dos filas como máximo; el Centro nunca recibe contraseñas ni
   SQL. La segunda fila solo indica si existe un registro siguiente.
5. El panel muestra campo, tipo y el **Valor** del registro actual. Todos los
   campos aparecen seleccionados inicialmente y el operador puede incluir o
   excluir cada uno.
6. Usar **Anterior**, **Siguiente** o **Ir al registro** para recorrer la
   vista. El salto está limitado a las posiciones 1–10.000 y cada movimiento
   crea una nueva consulta segura de dos filas como máximo, ordenada por la
   primera columna de la tabla. Es una vista de selección de campos; no define
   el orden de la sincronización.
7. Si se activa el filtro del año actual, la columna de fecha se selecciona de
   los campos inspeccionados.

Los identificadores se validan con una lista cerrada de caracteres, la
respuesta admite como máximo 256 campos y cada muestra de texto se trunca a
500 caracteres. Binarios se representan solo por su tamaño. Los previews se
eliminan del Centro al vencer y una tarea de mantenimiento los purga cada
cinco minutos.

Al pulsar **Crear y publicar**, el Centro valida los identificadores, verifica
que el motor coincida con la fuente, crea el catálogo, publica una versión
inmutable y registra ambas acciones en auditoría.

## Asignar el sincronizador a un agente

Crear un sync en el catálogo no lo activa en ninguna máquina por sí solo.

1. Ir a **Agentes → Asignación** y elegir el agente.
2. Pulsar **Agregar sync**.
3. Seleccionar el sincronizador habilitado del catálogo, su estado inicial y
   frecuencia.
4. Pulsar **Asignar**.

El Centro rechaza catálogos deshabilitados, duplicados y agentes cuya versión
no alcance el mínimo requerido. Al asignar, enlaza la última receta publicada,
incrementa la versión de configuración y registra auditoría. El agente la
descarga y verifica en su siguiente ciclo de configuración.

## Seguridad

- El formulario no recibe ni almacena credenciales de la base origen.
- No acepta SQL ni código Python.
- Solo permite inspeccionar mediante un agente online seleccionado
  explícitamente y deja auditoría de agente, perfil, motor y tabla.
- La receta entregada al agente queda incluida en la configuración Ed25519
  firmada.
- La tabla activa solo se reemplaza después de cargar y validar la sombra.
- `create_new` nunca debe apropiarse de una tabla operativa preexistente.

## Compatibilidad

La inspección remota paginada requiere el agente `0.6.4` o posterior. Los agentes
anteriores permanecen visibles en el selector, pero deshabilitados, para evitar
enviarles un tipo de comando que todavía no conocen.
