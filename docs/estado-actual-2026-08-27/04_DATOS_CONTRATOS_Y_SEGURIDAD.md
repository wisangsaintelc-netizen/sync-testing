# Datos, contratos y seguridad

## Modelo central vigente

| Entidad/tabla | Propósito |
|---|---|
| `users`, `personal_access_tokens` | Usuarios de control y tokens Sanctum. |
| `clients` | Cliente, sistema, estado y zona horaria. |
| `agents` | Identidad, equipo, versión, heartbeat, credencial hasheada, versión de config y destino MySQL cifrado. |
| `sync_sources` | Sistema administrativo, versión y motor lógico de base de datos. |
| `sync_catalog` | Código, clave funcional, dirección read/write, fuente, versión mínima, intervalo y habilitación global; soft deletes. |
| `agent_syncs` | Asignación, estado, intervalo, config, secretos cifrados y versión de receta fijada. |
| `sync_recipes`, `sync_recipe_versions` | Contenedor y publicaciones inmutables con versión, payload y SHA-256. |
| `sync_commands` | Comandos, payload, lease, expiración, idempotencia y resultado. |
| `sync_events` | Evento bruto idempotente recibido del agente. |
| `sync_runs` | Proyección operacional de cada ejecución, contadores, error y revisión. |
| `sync_audit_events` | Auditoría de acciones de control. |

No existe en las migraciones una tabla/columna de roles ni una entidad persistente para inspecciones; estas últimas viven temporalmente en `sync_commands.result_json`.

## Contrato de configuración del agente

El Centro entrega `schema_version`, `version`, `agent_code` y `syncs`. Desde agentes `>=0.2.0` usa schema `1.1` y puede incorporar `targets.bapps_mysql`. Cada asignación contiene estado, intervalo y, cuando aplica, receta, opciones y secretos.

El schema `docs/contracts/agent-config.v1.1.schema.json` quedó atrás: no define de forma estricta los items de `syncs`, ni refleja recetas, secretos, llavero, rotación o escritor. Debe considerarse referencia parcial, no validador completo del payload actual.

## Contrato de recetas de lectura

El schema JSON y el agente admiten:

- Firebird o SQL Server;
- columnas explícitas;
- predicados `eq`, `in`, nulos, ventana de año y combinaciones `and/or`;
- `parent_scope` con `EXISTS`;
- constantes;
- ownership;
- `full_snapshot` o `daily_history_v1`;
- transformación Profit autorizada;
- límites de lote, statement y runtime.

Hay dos tipos de drift:

1. El Centro `ReadRecipeValidationRules` no permite publicar toda la gramática que el schema/agente aceptan: no incluye `parent_scope`, `and/or` ni sus `predicates`, y la UI solo construye una ventana anual.
2. El agente valida pero no consume aún `schema_fingerprint`, `transformations`, `daily_history_v1`, `key_columns`, `statement_timeout_seconds` ni `max_runtime_seconds`.

Por tanto, el contrato documental es más amplio que el camino end-to-end certificado.

## Contrato del escritor

El escritor tiene reglas Laravel y tipos TypeScript, pero no existe un JSON Schema equivalente dentro de `docs/contracts`. El Centro valida motor, dirección, tablas conocidas, moneda `02`, 15 días, documento `PRS`, colisiones y lease. La asignación requiere perfil/depósito/estación/usuario/servidor/URL y token.

El agente usa un contrato privado externo:

- `POST /api/private/bapps-sync/v1/order-jobs/claim`;
- `POST /api/private/bapps-sync/v1/order-jobs/{id}/complete`;
- `POST /api/private/bapps-sync/v1/order-jobs/{id}/fail`.

Ese servidor y su esquema de base no forman parte de este repositorio; solo se certificó el cliente implementado aquí.

## Autenticación y autorización

### Agentes

- Enrolamiento con secreto hasheado.
- Rotación a token aleatorio en el primer enrolamiento válido.
- Solicitudes posteriores requieren bearer y `X-Agent-Code` coincidente.
- Agentes deshabilitados quedan rechazados.
- Claims/resultados están limitados al agente autenticado.

### Operadores

- Login con email/password y Sanctum.
- Token con capacidad `control-api`, duración 8 horas.
- Rate limit de 10 logins por minuto.

### Brecha RBAC

No existe autorización diferenciada. `LoginController` devuelve siempre `role: operator`; `AuthenticateControlApi` solo comprueba la capacidad genérica; los `FormRequest` permiten al usuario autenticado y no hay policies/gates. En consecuencia, cualquier usuario de control puede publicar recetas, inspeccionar datos, gestionar fuentes/catálogo y enviar comandos. Esto contradice la separación administrador/operador planteada en los documentos de diseño.

## Firma y confianza

El Centro puede firmar el payload completo con Ed25519 y soporta introducir una segunda clave mediante transición firmada. El agente enlaza la firma al `agent_code`, rechaza manipulación y downgrade, y protege el llavero local.

Brecha crítica: `ConfigSignatureVerifier._contains_declarative_recipe()` solo considera `declarative_table_reader`. Si el Centro no tiene clave privada configurada, una configuración que contenga exclusivamente `valery_prs_writer_v1` puede llegar sin firma y ser aceptada por el agente. La firma debe ser obligatoria para **todo motor de receta ejecutable**.

## Datos sensibles

- Laravel cifra arrays con `APP_KEY`; perder o rotar incorrectamente esa clave vuelve ilegibles los secretos.
- DPAPI `LocalMachine` permite que GUI administrativa y servicio `LocalSystem` compartan secretos, pero exige proteger permisos de archivos y el equipo.
- El frontend guarda bearer en `localStorage`, por lo que una vulnerabilidad XSS permitiría extraerlo.
- La inspección remota devuelve una muestra real de cada columna; aunque limita tamaño/tiempo y no expone credenciales, puede exponer datos personales o comerciales. Sin RBAC, la compuerta actual es insuficiente.
- Los mensajes del runner redactan patrones comunes de contraseña/token, pero no sustituyen una política de minimización de errores y revisión de logs.

## Contratos desactualizados

- Los schemas de comando/evento del paquete `backend-design` preceden a `inspect_source_table`, recetas y escritura.
- `agent-config.v1.1.schema.json` es permisivo/incompleto.
- No hay OpenAPI actual ni schema JSON del escritor.
- Los tipos actuales del frontend son más recientes que los mocks, lo que explica el fallo del typecheck.
