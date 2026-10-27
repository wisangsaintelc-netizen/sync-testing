# Estado del agente 0.6.0 candidato

Fecha de construcción: 2026-07-28.

## Resultado

Se generó un candidato instalable de BAPPS Sync Agent 0.6.0 sin modificar ni
reinstalar `AGT-VALERY-01` 0.5.4.

Artefactos:

| Archivo | Tamaño | SHA-256 |
|---|---:|---|
| `agent\release\BAPPS-Sync-Setup-0.6.0.exe` | 20.505.970 bytes | `CE70AF653BFBE3F6592B2F933EA6CCF7C113CC4950DC41D9C4D8DCD4509AF6D9` |
| `agent\release\BAPPS-Sync-Agent-0.6.0-windows-x64.zip` | 30.733.009 bytes | `A3CD83C850C5D8B47BED78D41012E72ECE3942AF741B6AD68911116D414F5A82` |

El Setup no tiene todavía firma Authenticode. No debe distribuirse como versión
general hasta incorporar un certificado de firma de código y el proceso de
timestamp. Para el piloto controlado se verifica por SHA-256.

## Alcance incorporado

- Motor declarativo único para recetas firmadas, sin descargar Python ni SQL
  libre desde el Centro.
- SQL Server/Profit mediante ODBC Driver 18 y Firebird/Valery mediante
  `firebirdsql`.
- Perfiles fuente con nombre y secretos locales protegidos con DPAPI.
- Snapshot Firebird y transacción snapshot SQL Server.
- Carga MySQL en tabla sombra, conteo previo y publicación por swap atómico.
- Propiedad de tablas por receta: una receta no puede sobrescribir la tabla de
  otra ni adoptar una tabla externa.
- Rechazo de versiones antiguas de configuración, retroceso de receta y recetas
  que exijan una versión de agente superior.
- Dependencias portables explícitas: PyMySQL, Firebird, pyodbc, cryptography,
  passlib, pywin32 y runtime Tcl/Tk del panel.

## Evidencia automatizada

- Agente: 69 pruebas correctas.
- Laravel: 39 pruebas, 231 aserciones.
- Sintaxis de `PublishSyncRecipeRequest.php`: correcta.
- Autoprueba del servicio empaquetado: correcta.
- Autoprueba del panel empaquetado: código 0.
- Smoke test del panel contra estado temporal: permaneció operativo durante la
  comprobación.
- Autopruebas repetidas desde la carpeta final de distribución: correctas.

## Límite de esta entrega

El artefacto está construido y validado estáticamente, pero no se instaló. Aún
faltan los gates físicos del piloto:

1. desplegar/migrar recetas en el Centro;
2. crear una identidad separada `AGT-VALERY-PILOTO`;
3. instalar 0.6.0 en la segunda PC o VM aislada;
4. probar conexión Firebird de solo lectura y MySQL piloto;
5. publicar/asignar la receta inicial de `CLIENTES`;
6. comparar origen, sombra y destino;
7. ejecutar la matriz de resiliencia, incluida outbox de 10.000 eventos.

La UI completa para crear recetas, la inspección segura de tablas y columnas,
el RBAC administrativo y el harness de fallos siguen siendo gates antes de
declarar 0.6.0 lista para producción.

## Construcción reproducible

El script `agent\scripts\build_portable.ps1` admite un runtime Tcl/Tk explícito
cuando el Python de compilación no incluye los datos Tcl/Tk. Esto evita generar
silenciosamente un panel incompleto. Para futuras compilaciones debe
estandarizarse un entorno de build con Python completo y certificado; la PC
cliente no necesita Python.
