# BAPPS Sync Agent 0.7.10

Agente Windows de BAPPS Sync. Ejecuta sincronizadores de lectura configurados
desde el Centro de Operaciones, conserva una outbox durable y usa el mismo
motor para ejecuciones manuales y programadas.

## Lecturas declarativas y escritor Valery PRS 0.7.10

Cuando una sincronización falla de forma inesperada, el agente conserva en el
resultado el tipo de excepción y su mensaje técnico útil (por ejemplo, error
de conexión o de tabla), con un límite de longitud. Antes de persistirlo o
enviarlo al Centro, oculta contraseñas, tokens, secretos y credenciales dentro
de URL. Esto permite depurar desde **Ejecuciones** sin exponer secretos.

Un comando manual `run_now` se muestra como **Enviado** cuando el agente lo
acepta; su resultado final se consulta en **Ejecuciones**, pues el trabajo se
realiza en segundo plano.

La protección local DPAPI del destino MySQL no altera el documento firmado: al
recuperar la configuración, el agente elimina la marca interna de protección
antes de volver a verificar la firma Ed25519.

Después de una publicación atómica, el agente elimina su respaldo temporal
`__bapps_old_<id>`. Al iniciar una publicación también purga residuos
históricos que coincidan exactamente con ese patrón interno; no toca tablas
operativas, legacy ni nombres fuera de ese formato.

Las tablas publicadas por recetas declarativas incluyen siempre
`id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`; ese identificador es local al
destino y no se toma de Profit o Valery.

## Hotfix 0.6.1

Esta versión incorpora el motor declarativo de lectura:

- el Centro define la tabla, columnas, filtros y destino;
- la configuración completa viaja firmada con Ed25519;
- el agente valida firma, identidad, versión y vigencia antes de guardarla;
- las credenciales de la base fuente permanecen en la máquina del cliente;
- una receta puede leer SQL Server (Profit) o Firebird (Valery);
- el destino MySQL se carga primero en una tabla temporal y se publica mediante
  un intercambio atómico;
- el agente no permite que una receta se apropie de una tabla administrada por
  otra receta ni que retroceda su versión;
- la tabla anterior continúa visible si la lectura o la carga falla.

El agente 0.6.1 no ejecuta SQL arbitrario recibido desde el Centro. Solo acepta
el contrato declarativo y los operadores incluidos en el binario.

## Configuración local

El panel portable permite crear perfiles de conexión fuente con nombre. Las
credenciales se almacenan bajo:

```text
C:\ProgramData\Bapps\SyncAgent\config
```

Los secretos se protegen con DPAPI y no se envían al Centro BAPPS. Para el
piloto debe usarse un usuario de solo lectura en Firebird o SQL Server y un
usuario MySQL limitado a la base destino administrada por BAPPS Sync.

Durante desarrollo:

```powershell
python -m bapps_sync_agent.ui_main --state-dir C:\ProgramData\Bapps\SyncAgent
```

## Pruebas

Desde la raíz del repositorio:

```powershell
& 'agent\.venv\Scripts\python.exe' -m unittest discover -s agent\tests -p 'test_*.py'
```

## Construcción Windows

Portable:

```powershell
.\agent\scripts\build_portable.ps1 `
  -Python '.\agent\.venv\Scripts\python.exe' `
  -SkipDependencies
```

Instalador:

```powershell
.\agent\scripts\build_installer.ps1 -Version 0.6.1 `
  -TrustBundle .\agent\build\config-signing-trust.json
```

Antes de distribuir, deben ejecutarse las autopruebas de ambos binarios:

```powershell
.\agent\dist\BAPPS-Sync-Agent\BAPPS-Sync-Agent.exe --portable-self-test
.\agent\dist\BAPPS-Sync-Service\BAPPS-Sync-Service.exe --portable-self-test
```

El instalador candidato no debe reemplazar el servicio estable 0.5.4 hasta
completar el piloto aislado descrito en `docs\PILOTO_INTEGRAL_VALERY.md`.
