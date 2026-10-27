# BAPPS Sync: estado actual certificado

Fecha de corte: **2026-08-27**  
Repositorio auditado: `C:\Sync\Valery\bapps-sync`

Esta carpeta consolida el estado real de BAPPS Sync después de releer la documentación existente y contrastarla con el código, las migraciones, las rutas, los contratos, las pruebas y los artefactos disponibles. No reemplaza el historial: lo ordena y distingue con claridad de la implementación vigente.

## Cómo leer este paquete

1. [01_ESTADO_EJECUTIVO.md](01_ESTADO_EJECUTIVO.md): producto, versión y conclusión de la auditoría.
2. [02_ARQUITECTURA_Y_FLUJOS.md](02_ARQUITECTURA_Y_FLUJOS.md): componentes, almacenes y recorridos de datos certificados.
3. [03_COMPONENTES_IMPLEMENTADOS.md](03_COMPONENTES_IMPLEMENTADOS.md): Centro Laravel, frontend React y agente Windows.
4. [04_DATOS_CONTRATOS_Y_SEGURIDAD.md](04_DATOS_CONTRATOS_Y_SEGURIDAD.md): modelo de datos, contratos, autenticación y límites de confianza.
5. [05_VERIFICACION_REPRODUCIBLE.md](05_VERIFICACION_REPRODUCIBLE.md): resultados obtenidos y comandos para repetirlos.
6. [06_BRECHAS_RIESGOS_Y_PROXIMOS_PASOS.md](06_BRECHAS_RIESGOS_Y_PROXIMOS_PASOS.md): diferencias verificadas entre intención e implementación.
7. [07_TRAZABILIDAD_DOCUMENTAL.md](07_TRAZABILIDAD_DOCUMENTAL.md): vigencia de los documentos anteriores y fuentes de verdad.
8. [08_MATRIZ_DE_CERTIFICACION.md](08_MATRIZ_DE_CERTIFICACION.md): veredicto elemento por elemento y evidencia primaria.
9. [data/estado-producto.json](data/estado-producto.json): resumen estructurado para consumo automático.
10. `data/inventario-documental.json`: inventario reproducible de todos los artefactos documentales anteriores a esta carpeta, con tamaño y SHA-256.

## Semántica de certificación

| Estado | Significado |
|---|---|
| `IMPLEMENTADO` | Existe un recorrido ejecutable completo en el código vigente. |
| `PROBADO` | Fue ejercitado satisfactoriamente durante este corte o por una prueba automatizada identificable. |
| `ARTEFACTO_VERIFICADO` | El archivo existe y se comprobó su tamaño, hash, firma o auto-test. |
| `PARCIAL` | Parte del comportamiento existe, pero faltan piezas declaradas por el contrato o la documentación. |
| `PENDIENTE_ACEPTACION` | La implementación existe, pero requiere una validación física u operacional externa. |
| `NO_VERIFICABLE_LOCALMENTE` | Depende de despliegues, bases, credenciales, equipos o aplicaciones fuera de este repositorio. |
| `HISTORICO` | Conserva valor de contexto, pero no describe por sí solo el producto vigente. |
| `CONTRADICHO` | El código actual demuestra que la afirmación ya no es cierta. |

## Regla de fuente de verdad

Para determinar el presente se usó este orden: código y migraciones vigentes; pruebas ejecutadas; artefactos verificables; documentos fechados más recientes; planes y paquetes históricos. Una casilla marcada en un plan nunca se consideró evidencia suficiente por sí sola.

## Alcance y límites

Se inventariaron **201 archivos** previos dentro de `docs` (440.036.959 bytes), incluidos 51 Markdown, 12 JSON, 7 HTML y artefactos binarios/históricos. Se leyó el contenido documental y contractual; los ejecutables, ZIP, bytecode y salidas de PyInstaller se trataron como artefactos, no como prosa.

No se usó ni modificó una base productiva. Tampoco se accedió al equipo físico `AGT-VALERY-01`, al Valery Administrator ni al repositorio de la API privada de pedidos. Por ello, ningún resultado que dependa de esos sistemas se presenta como validado localmente.
