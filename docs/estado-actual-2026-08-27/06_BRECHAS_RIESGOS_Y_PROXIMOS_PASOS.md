# Brechas, riesgos y próximos pasos

## Prioridad 0: cierre seguro del piloto

### 1. Aceptación física del escritor PRS

Estado: `PENDIENTE_ACEPTACION`.

Instalar el artefacto candidato, generar un pedido nuevo y validar el PRS dentro de Valery Administrator. Conservar evidencia del pedido, job, run, correlativo/documento, tablas afectadas y capturas del resultado funcional. Sin esta prueba, `0.7.10` sigue siendo candidato técnico.

### 2. Firma obligatoria para el escritor

Estado: brecha de seguridad `IMPLEMENTADA_INCORRECTAMENTE`.

Ampliar la detección de recetas firmables para incluir `valery_prs_writer_v1` y cualquier motor futuro. El Centro debería fallar cerrado al proyectar recetas cuando la clave privada no está configurada, en lugar de entregar un payload ejecutable sin firma.

### 3. RBAC real

Estado: `NO_IMPLEMENTADO`.

Definir roles persistentes y policies/gates. Como mínimo separar:

- lectura/observabilidad;
- operación de runs y pausas;
- configuración de agentes;
- inspección de datos fuente;
- administración de fuentes/catálogo;
- publicación de recetas y escritores.

La inspección y publicación deben ser capacidades de alto privilegio con pruebas negativas.

### 4. Firma Authenticode

Estado: `NO_IMPLEMENTADO` en el artefacto.

Firmar y timestamp el instalador y, preferiblemente, los binarios internos. Registrar sujeto, cadena, timestamp y hash en el acta de release.

## Prioridad 1: coherencia y calidad

### 5. Corregir typecheck y hacerlo compuerta

Agregar `direction` a los siete objetos de mocks, crear script `typecheck` y ejecutar build + typecheck en CI. Los mocks no deben quedar como contrato alternativo atrasado.

### 6. Rehacer el entorno Python

Recrear `.venv` desde Python 3.11/3.12 soportado, fijar dependencias reproducibles y re-ejecutar las 106 pruebas. El release no debe depender de una ruta efímera de Codex.

### 7. Alinear contratos

- Hacer coincidir JSON Schema, validación Laravel, tipos TypeScript y parser Python.
- Crear schema del escritor.
- Actualizar command/event/config schemas.
- Agregar pruebas contractuales con los mismos fixtures en Centro y agente.
- Decidir si `parent_scope`, `and/or`, `eq/in` serán publicables ahora o se retiran temporalmente del schema.

### 8. No aceptar opciones que no se ejecutan

Antes de exponerlas en producción, implementar o rechazar explícitamente:

- `schema_fingerprint`;
- `daily_history_v1` y `key_columns`;
- `profit.article_tax_rate_v1`;
- `statement_timeout_seconds`;
- `max_runtime_seconds`.

Hoy esas opciones crean una falsa sensación de cumplimiento.

## Prioridad 2: operación y escala

### 9. Matriz de resiliencia

Ejecutar con evidencia: Centro caído, fuente caída, MySQL caído, disco lleno, outbox grande, reinicio, lease vencido, doble run, stop race, schema drift, tabla destino ajena, rotación de clave, 24 horas de soak, tres agentes concurrentes y tormenta de reconexión. Las pruebas unitarias cubren mecanismos, no sustituyen aceptación operacional.

### 10. Capacidad de outbox y disco

La outbox no tiene cuota, compactación ni política de retención. Definir alertas, umbrales, conducta ante disco lleno y recuperación de `failed`. El heartbeat ya reporta cantidad y bytes, pero el Centro/UI no cierran toda la operación de backlog.

### 11. Concurrencia del escritor

La numeración usa `MAX()+1` y reintenta colisiones; esto reduce fallos, pero no equivale a una reserva serializada por generador. Validar bajo concurrencia real y, si Valery ofrece generadores/secuencias oficiales, preferirlos.

### 12. Sesiones de control

Agregar logout/revocación explícita, política de password/usuarios y considerar almacenamiento de sesión menos expuesto a XSS. Asegurar CSP y auditoría de autenticaciones fallidas/exitosas.

### 13. Deploy reproducible

Crear pipeline o checklist ejecutable que verifique dependencias, tests, typecheck, Pint, migraciones, config cache, llaves, TLS, backups y health checks. No hay configuración CI visible en el repositorio.

## Deuda documental

1. Reescribir el `README.md` raíz: el backend ya no es una fase futura y el login no acepta cualquier contraseña.
2. Marcar los handoffs/estados viejos como históricos sin borrarlos.
3. Mantener un único changelog de agente y una sola ficha de release.
4. Evitar duplicar el Development Pack dentro de `backend-design`.
5. Regenerar schemas y documentación de API a partir de contratos testeados.

## Criterio recomendado de “producción lista”

BAPPS Sync podrá declararse listo para el piloto cuando P0 esté cerrado, todas las suites sean reproducibles y verdes, typecheck pase, el instalador esté firmado, los contratos sean coherentes y exista evidencia física del PRS. Para despliegue general deben cerrarse además resiliencia, observabilidad de outbox, operación de llaves/backups y pruebas multiagente.
