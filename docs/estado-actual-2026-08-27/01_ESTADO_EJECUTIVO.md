# Estado ejecutivo

## Conclusión

BAPPS Sync ya no es un frontend con mocks a la espera de backend. Es un producto integrado compuesto por:

- un Centro de Control Laravel 13 con API, persistencia, autenticación, auditoría, comandos y proyección de eventos;
- una SPA React 19 que opera por defecto contra la API real;
- un agente Windows Python `0.7.10`, con servicio, panel, enrolamiento, scheduler, outbox, ejecución serializada y conectores Firebird, SQL Server y MySQL;
- un motor declarativo de lectura con publicación por tabla sombra;
- un escritor especializado `valery_prs_writer_v1` para convertir pedidos autorizados en presupuestos `PRS` dentro de Valery.

El producto está técnicamente avanzado, pero **todavía no puede declararse cerrado para producción general**. El escritor PRS conserva como compuerta principal la aceptación física de un pedido nuevo dentro de Valery Administrator. También faltan controles de seguridad y coherencia contractual relevantes: RBAC real, firma obligatoria del escritor, typecheck limpio, alineación de schemas y ejecución real de varias opciones aceptadas por la receta de lectura.

## Foto certificada

| Área | Estado | Evidencia y lectura correcta |
|---|---|---|
| Centro Laravel | `IMPLEMENTADO` y `PROBADO` | 31 rutas API: 6 para agente y 25 de control, incluida autenticación. Suite: 48/48 pruebas, 279 aserciones. |
| Frontend React | `IMPLEMENTADO`, build `PROBADO` | SPA real con dashboard, agentes, asignación, ejecuciones, auditoría, clientes y catálogo. Vite transforma 115 módulos. |
| TypeScript estricto | `PARCIAL` | `npx tsc --noEmit` falla con 7 errores: los mocks de catálogo no contienen el nuevo campo obligatorio `direction`. |
| Agente Windows | `IMPLEMENTADO` | Fuente y empaquetado declaran `0.7.10`; servicio Windows, GUI, DPAPI, perfiles locales, scheduler, comandos y outbox. |
| Pruebas Python | `NO_VERIFICABLE_LOCALMENTE` en este corte | Hay 106 métodos de prueba. El documento vigente reporta 106 exitosos, pero la `.venv` apunta a un Python eliminado y no pudo re-ejecutarse. |
| Auto-test portable | `PROBADO` | GUI portable finaliza con código 0; servicio informa `BAPPS Sync Service: self-test correcto.` |
| Instalador 0.7.10 | `ARTEFACTO_VERIFICADO` | 20.752.719 bytes; SHA-256 `2223C91B9E827088C458B5FB6341D13900852899D0B98750BC621D0A16E36715`. |
| Firma Authenticode | `PENDIENTE_ACEPTACION` | El instalador `0.7.10` devuelve `NotSigned`. |
| Lectura declarativa | `PARCIAL` | Snapshot consistente, shadow/swap, conteo y ownership sí; histórico diario, huella, transformaciones y timeouts aún no se ejecutan. |
| Escritor Valery PRS | `PENDIENTE_ACEPTACION` | Flujo, idempotencia, transacción y validaciones están implementados y cubiertos por pruebas de fuente; falta aceptación física final en Valery. |
| RBAC | `CONTRADICHO` respecto al diseño | Existe autenticación, pero todos los usuarios autenticados reciben capacidad `control-api`; el rol `operator` está fijado en el JSON y no hay roles, policies ni gates. |
| Producción | `NO_VERIFICABLE_LOCALMENTE` | El repositorio contiene guía de despliegue, no evidencia suficiente del estado actual de servidor, BD, TLS, llaves, backups o equipos instalados. |

## Versión y artefactos

- Paquete Python: `0.7.10` en `agent/pyproject.toml` y `agent/src/bapps_sync_agent/__init__.py`.
- Instalador NSIS por defecto: `0.7.10`.
- Artefacto candidato: `agent/release/BAPPS-Sync-Setup-0.7.10.exe`.
- Fecha del artefacto observada: 2026-07-31 09:54:46 local.
- Último cierre documental relevante: actualización del 2026-08-03 en `ONGOING.txt` y `HANDOFF_CONTINUACION_2026-07-27.md`.

## Estado funcional por objetivo

### Operación central

El operador puede autenticarse, ver métricas, clientes, agentes, ejecuciones y auditoría; crear y mantener fuentes/catálogo; publicar recetas; configurar MySQL del agente; asignar syncs; ejecutar, pausar, reanudar y detener; revisar y reintentar fallos; e inspeccionar una fila remota de una tabla fuente mediante un agente online.

### Lecturas hacia BAPPS MySQL

Hay dos caminos:

- `clientes_valery`, sincronizador Python legado/especializado, hace upsert por `CODIGO`.
- `declarative_table_reader`, motor genérico firmado para Firebird o SQL Server, crea una sombra y publica por `RENAME TABLE` solamente después de cargar y validar el conteo.

La promesa de “motor único” está encaminada, no completada: el sincronizador especializado sigue coexistiendo y varias capacidades declarativas todavía son solo contrato.

### Escritura de pedidos a Valery

El escritor reclama un trabajo de la API privada de pedidos, comprueba idempotencia por `VENTAS.TIPO_DOCUMENTO='PRS'` más `ORDEN_DE_COMPRA`, obtiene maestros, calcula importes, escribe en una sola transacción Firebird y reporta finalización o fallo. Inserta cabecera/detalles y registros auxiliares en `VENTAS`, `VENTAS_AD`, `VENTAS_ESTADOS`, `VENTAS_EXT`, `VENTAS_DETALLES` y, cuando hay texto, `VENTAS_DETALLES_EXT`.

La aceptación pendiente no es cosmética: debe probar que Valery Administrator interpreta el documento creado exactamente como se espera en una instalación real.

## Documentos que no deben usarse solos

- El `README.md` raíz está obsoleto: afirma que el backend real es “la siguiente fase”.
- `PILOTO_INTEGRAL_VALERY.md` conserva una fotografía del 2026-07-28 y marca como pendientes UI/API que luego sí fueron implementadas.
- Los estados `0.6.x` y el estado portable describen hitos e incidentes históricos, no la versión vigente.
- El paquete `backend-design` contiene duplicados y contratos de diseño que no fueron actualizados con comandos, tablas y motores posteriores.
