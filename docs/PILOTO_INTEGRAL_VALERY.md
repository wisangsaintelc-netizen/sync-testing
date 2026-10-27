# Piloto integral Valery: receta, sincronización y resiliencia

## Propósito

Validar la fórmula completa de BAPPS Sync con Firebird Valery real, sin alterar
\`AGT-VALERY-01\` 0.5.4 ni \`clientes_valery_sync\`.

\`\`\`text
Centro firmado → agente candidato → receta declarativa → Firebird Valery
→ MySQL BAPPS piloto (sombra/swap) → outbox → Centro/auditoría
\`\`\`

No es una prueba de escritura hacia Valery/Profit: el origen se usa solo en
lectura.

## Gates actuales

| Gate | Estado | Pendiente antes de prueba física |
|---|---|---|
| Centro y firma Ed25519 | Código/runtime validados | Desplegar y migrar recetas |
| Catálogo/fuentes | Operativo | Crear fuente/catálogo de piloto |
| Publicar receta | API inicial | UI, RBAC admin y pruebas |
| Inspección/preview | Pendiente | Protocolo limitado, enmascarado, auditado |
| Motor Firebird declarativo | Unit tests | Empaquetar y probar agente candidato |
| Sombra/swap MySQL | Unit tests | MySQL piloto y permisos mínimos reales |
| Resiliencia | Matriz definida | Harness y fallos aislados |

La API de recetas no sustituye todavía la creación completa desde el panel. No
se habilita para operación hasta cerrar UI, inspección segura y RBAC admin.

## Aislamiento obligatorio

### Agente

- Instalar un candidato distinto, por ejemplo \`AGT-VALERY-PILOTO\`, en otra PC
  o VM Windows. No reutilizar su identidad ni estado DPAPI del agente estable.
- Si comparte host, debe ser una VM; no se ejecutan dos servicios sobre el
  mismo estado local.
- El candidato recibe solo la clave pública de firma al enrolarse. La privada
  nunca sale del \`.env\` del Centro.

### Firebird Valery

- Perfil DPAPI local: \`valery_piloto\`.
- Usuario dedicado de solo lectura.
- Primera tabla: \`CLIENTES\`; permite comparar contra las 369 filas previamente
  validadas. No modificar datos del origen durante el piloto.

### MySQL BAPPS

- Base/instancia exclusiva, por ejemplo \`bapps_sync_pilot\`.
- Tabla inicial: \`clientes_valery_pilot\`; no usar \`clientes_valery_sync\`.
- Usuario limitado a la base piloto y a los permisos de \`CREATE\`, \`INSERT\`,
  \`SELECT\`, \`ALTER\`, \`DROP\` y \`RENAME\` indispensables para sus tablas.
- La primera receta debe usar \`create_new\`; no se adoptan tablas legacy.

## Receta inicial

El panel deberá producir una receta equivalente, sin SQL libre. Las columnas
finales se eligen de la inspección real y se guardan explícitamente:

\`\`\`json
{
  "schema_version": "1.0",
  "recipe_code": "valery_clientes_snapshot_pilot",
  "engine": "declarative_table_reader",
  "minimum_agent_version": "0.6.0",
  "source": {
    "profile_ref": "valery_piloto",
    "driver": "firebird",
    "table": "CLIENTES",
    "columns": ["CODIGO", "NOMBRE"]
  },
  "target": {
    "profile_ref": "bapps_mysql",
    "table": "clientes_valery_pilot",
    "strategy": "full_snapshot",
    "ownership": "create_new"
  },
  "limits": {"batch_rows": 200, "statement_timeout_seconds": 60, "max_runtime_seconds": 900}
}
\`\`\`

Publicar debe registrar fingerprint, hash, versión, administrador y fecha.

## Secuencia de aceptación funcional

### F0 — Centro

1. Respaldar \`bapps_sync\` y \`.env\`.
2. Desplegar según \`DEPLOY_CENTRO_LARAVEL.md\`.
3. Aplicar \`2026_07_28_010000_create_sync_recipes_tables.php\` con
   \`php artisan migrate --force\`.
4. Confirmar HTTPS, \`APP_DEBUG=false\`, login y firma de configuración sin
   exposición de la clave privada.

### F1 — Agente candidato

1. Empaquetar instalador con motor declarativo, verificador Ed25519 y Firebird.
2. Instalar/enrolar \`AGT-VALERY-PILOTO\` y confirmar heartbeat.
3. Crear perfiles DPAPI \`valery_piloto\` y \`bapps_mysql\`.
4. Ejecutar preflight de Firebird, MySQL 8/InnoDB, permisos, espacio y outbox.

### F2 — Panel y receta

1. Como admin, crear fuente \`Firebird → Valery → versión\` y catálogo
   \`clientes_valery_pilot\`.
2. Inspeccionar \`CLIENTES\` con preview limitado; no guardar datos en auditoría.
3. Seleccionar columnas, límites y destino; publicar receta v1.
4. Asignar v1 al candidato y verificar firma, destinatario y monotonicidad.
5. Confirmar que \`operator\` recibe 403 al inspeccionar/publicar y que queda
   auditoría del intento.

### F3 — Datos y evolución

1. Ejecutar \`run_now\`: destino primero, snapshot Firebird, sombra, validación y
   swap atómico.
2. Comparar conteo origen/destino, muestra normalizada, nulos y duplicados.
3. Repetir la ejecución: nunca hay \`TRUNCATE\` ni modificación parcial de la
   tabla activa.
4. Publicar v2 con una columna adicional y comprobar nueva sombra/swap y
   conservación temporal de la versión anterior.

## Matriz de resiliencia

Cada fallo se ejecuta solo contra agente y destino piloto. Antes/después se
registra hash de receta, conteos y tabla activa.

| Caso | Inyección aislada | Resultado exigido |
|---|---|---|
| MySQL inaccesible antes de iniciar | Bloquear puerto en VM piloto | No abrir Firebird; evento durable |
| MySQL cae durante carga | Detener solo instancia piloto | Activa intacta; sin publicación parcial |
| Reinicio antes de swap | Detener candidato en punto de prueba | Journal recupera; una activa visible |
| Outbox sin espacio/permisos | VHD pequeño o directorio de prueba | No inicia si no persiste evento; \`blocked\` |
| MySQL sin espacio | Cuota/instancia limitada | Activa intacta; no swap |
| DNS/red intermitente | Host de prueba/firewall VM | Backoff+jitter; no pierde eventos |
| TLS inválido | Endpoint de prueba con CA no confiable | Rechaza; nunca desactiva TLS |
| HTTP 429/5xx | Stub de Centro para candidato | Respeta \`Retry-After\`; outbox consistente |
| Outbox 10.000 | Generador sintético local | Cero pérdida/corrupción; control responsivo |
| Esquema cambia | Receta/fingerprint de laboratorio | Bloquea antes de swap |
| Destino ajeno | Tabla manual sin marcador | \`TARGET_TABLE_NOT_MANAGED\`; cero DDL |
| Permisos insuficientes | Usuario limitado de laboratorio | Preflight indica permiso faltante |

Nunca llenar discos reales, cortar la red de la PC estable ni usar TLS inválido
contra el Centro productivo.

## Aprobación y evidencia

El piloto pasa solo con: preflight sin secretos; hash/versión y acuse firmado;
conteos/digest origen-sombra-activa; logs/eventos de cada fallo; estado
operativo visible en Centro; y evidencia de que el agente/tabla estables no se
tocaron.

Firma inválida, pérdida de evento, swap parcial, escritura sobre tabla ajena,
exposición de secretos o TLS desactivado bloquean el piloto y obligan a corregir
código antes de repetirlo.

## Orden inmediato

1. Implementar UI/RBAC y pruebas de recetas.
2. Implementar inspección/preview limitado y auditado.
3. Añadir harness: 10.000 eventos, persistencia/reintentos y fallos de destino.
4. Empaquetar \`AGT-VALERY-PILOTO\`; ejecutar F0–F3 en una VM/PC aislada.
5. Ejecutar toda la matriz y aprobar/rechazar la fórmula Firebird antes de
   llevarla a Profit/SQL Server.

