# Trazabilidad documental

## Regla de vigencia

La fecha del nombre no basta: algunos documentos antiguos fueron editados después. Se contrastó contenido, versión citada, código vigente y evidencia reproducible.

## Documentos raíz

| Documento | Clasificación | Uso correcto hoy |
|---|---|---|
| `ARQUITECTURA_SINCRONIZADORES_Y_DATOS.md` | `VIGENTE_CON_MATICES` | Fuente conceptual principal para separación Centro/agente/almacenes y recetas versus código empaquetado. |
| `BAPPS_SYNC_PLAN_MAESTRO_v1.1.md` | `HISTORICO_DE_DISEÑO` | Arquitectura, contratos y QA base; sus checklists no prueban implementación actual. |
| `CONTROL_RUNTIME_AUTOMATICO.md` | `VIGENTE` | Describe scheduler, heartbeat, comandos y servicio; verificar constantes contra código. |
| `CREAR_SINCRONIZADOR_DESDE_CATALOGO.md` | `VIGENTE_CON_BRECHAS` | Flujo UI/API e inspección implementados; RBAC admin-only no existe. |
| `DEPLOY_CENTRO_LARAVEL.md` | `GUIA_VIGENTE_NO_EVIDENCIA` | Procedimiento útil; no certifica que producción esté desplegada/configurada así. |
| `ESPECIFICACION_MOTOR_UNICO_LECTURA_PROFIT_2026-07-27.md` | `PARCIALMENTE_IMPLEMENTADO` | Define destino correcto; varias opciones aceptadas siguen sin ejecución. |
| `ESTADO_AGENTE_0.6.0_CANDIDATO.md` | `HISTORICO` | Antecedente de firma/instalador. |
| `ESTADO_AGENTE_0.6.1_HOTFIX.md` | `HISTORICO` | Incidente y corrección previos. |
| `ESTADO_AGENTE_0.6.2_FIRMA_Y_ESTADO.md` | `HISTORICO` | Evolución de confianza/config; superado por 0.7.10. |
| `ESTADO_AGENTE_PORTABLE_2026-07-17.md` | `HISTORICO_EXTENSO` | Cronología de portable, enrolamiento, DPAPI, servicio e instalador. |
| `ESTADO_IMPLEMENTACION.md` | `HISTORICO` | Foto temprana; no representa el backend/escritor actual. |
| `GUIA_PRUEBA_VERTICAL.md` | `HISTORICO_PARCIAL` | Útil para smoke inicial; la afirmación de no tener sync real quedó superada. |
| `HANDOFF_CONTINUACION_2026-07-23.md` | `HISTORICO` | Handoff de una etapa anterior. |
| `HANDOFF_CONTINUACION_2026-07-27.md` | `VIGENTE_EN_SU_CIERRE` | El final actualizado al 03-08 es fuente del candidato 0.7.10; secciones intermedias 0.5/0.6 son históricas. |
| `ONGOING.txt` | `VIGENTE` | Registro breve más reciente: 0.7.10, hash y aceptación física pendiente. |
| `PILOTO_INTEGRAL_VALERY.md` | `HISTORICO_PARCIAL` | Matriz de piloto/resiliencia útil; varias UI/API marcadas pendientes ya existen. |
| `PLAN_CONTINUACION_2026-07-22.md` | `HISTORICO` | Plan de transición. |
| `PLAN_IMPLEMENTACION_FRONTEND_v1.0.md` | `HISTORICO_DE_IMPLEMENTACION` | Explica decisiones visuales/mocks-first; backend ya fue implementado. |
| `PLAN_RESILIENCIA_Y_RECETAS_LECTURA_2026-07-27.md` | `OBJETIVO_PARCIAL` | Requisitos de seguridad/resiliencia; no asumir su matriz como aprobada. |
| `VALERY_PRS_WRITER_V1.md` | `VIGENTE` | Especificación más cercana al escritor 0.7.10 y su compuerta física pendiente. |
| `example bapps agent config.jpg` | `REFERENCIA_VISUAL_HISTORICA` | Ejemplo, no contrato. |

## Subdirectorios

### `backend-design`

Contiene 175 archivos y aproximadamente todo el peso documental por incluir ZIP, binarios, bytecode y resultados PyInstaller. Hay dos copias equivalentes del Development Pack (`BAPPS_Sync_Development_Pack_v1.1` y `develop-docs`) y una especificación v1.0 anterior. Debe conservarse como baseline/archivo histórico, no como fuente de verdad operativa.

Sus documentos de arquitectura, API, contratos, datos, QA, roadmap, playbook, ADR y aceptación se revisaron como intención. Los schemas y ejemplos preceden a `inspect_source_table`, `sync_sources`, recetas firmadas y dirección write.

### `frontend-design`

El sistema visual y la guía técnica siguen reflejándose en el frontend: IBM Plex, navy, estados centralizados, filtros/tablas y drawers. La maqueta `standalone.html` es una referencia de diseño simulada, no la aplicación vigente.

### `contracts`

- `read-recipe-v1.schema.json`: la gramática más completa, pero más amplia que el Centro y que la ejecución efectiva.
- `agent-config.v1.1.schema.json`: incompleto para la configuración actual.

## Afirmaciones documentales corregidas por código

| Afirmación previa | Estado real |
|---|---|
| “El backend real es la siguiente fase.” | Contradicha: hay API, migraciones, acciones y 48 pruebas Laravel. |
| “Login demo acepta cualquier contraseña.” | Contradicha en modo real: usa usuario y hash Laravel. |
| “Publicación/inspección solo admin.” | Contradicha: no hay RBAC; cualquier token `control-api` puede hacerlo. |
| “Motor único completo.” | Parcial: convive `clientes_valery` y faltan capacidades declarativas. |
| “Configuraciones con recetas siempre firmadas.” | Cierto para lector declarativo, no forzado para writer-only. |
| “Schema fingerprint evita drift.” | No implementado en runtime. |
| “Daily history v1.” | Se valida pero se publica como snapshot normal. |
| “QA de resiliencia completado.” | No hay evidencia local suficiente; solo pruebas unitarias de mecanismos. |
| “0.7.10 listo.” | Candidato técnico; aceptación física y Authenticode pendientes. |

## Inventario completo

`data/inventario-documental.json` registra cada uno de los 201 archivos anteriores con ruta relativa, extensión, tamaño, fecha y SHA-256, además de grupos de contenido duplicado. Se genera con `tools/generar-inventario-documental.ps1`, excluyendo esta carpeta para evitar autocontaminación.
