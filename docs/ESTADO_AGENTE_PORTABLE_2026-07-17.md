# Estado del agente portable - 2026-07-17

Este documento resume con precision lo realizado hasta ahora en el agente Python de BAPPS Sync y el primer portable Windows con interfaz grafica.

## Resultado actual

Se construyo la primera entrega portable del agente local:

- Ejecutable generado: `agent/dist/BAPPS-Sync-Agent/BAPPS-Sync-Agent.exe`
- Tamano del `.exe`: 2,771,159 bytes
- Carpeta portable completa: `agent/dist/BAPPS-Sync-Agent/`
- Contenido portable medido: 980 archivos, 32,656,384 bytes
- Empaquetador usado: PyInstaller
- Runtime incluido: Python 3.12, Tk/Tkinter, dependencias Firebird y MySQL

La carpeta portable completa es lo que se debe copiar a otra maquina. El `.exe` solo no basta, porque PyInstaller dejo librerias y runtime dentro de `_internal`.

## Alcance implementado

### 1. Interfaz grafica local

Archivos principales:

- `agent/src/bapps_sync_agent/ui/app.py`
- `agent/src/bapps_sync_agent/ui_main.py`

La interfaz usa Tkinter para mantener el portable simple y sin dependencias visuales externas.

La ventana actual muestra:

- Centro BAPPS en modo solo lectura.
- Codigo/identidad del agente, si ya existe enrolamiento local.
- Estado de configuracion MySQL BAPPS recibida desde el panel central.
- Configuracion local de la base que el agente va a leer.
- Botones para actualizar estado, guardar configuracion y probar conexion.

La configuracion editable desde el agente queda limitada a la base fuente local, como se definio:

- Motor: `firebird` o `mysql`
- Host/IP
- Puerto
- Base, ruta o alias
- Usuario
- Contrasena

### 2. Separacion de responsabilidades

Quedo respetada la frontera acordada:

- El Centro BAPPS / URL Laravel no se configura como dato libre dentro del panel local.
- El MySQL de BAPPS no se configura desde el agente; se espera como configuracion administrada por el panel central.
- El agente local solo configura la base fuente que va a leer: Valery, Profit u otra fuente compatible.
- La credencial de la base fuente queda local en la maquina del cliente.

### 3. Almacenamiento seguro local

Archivos:

- `agent/src/bapps_sync_agent/infrastructure/secret_protector.py`
- `agent/src/bapps_sync_agent/infrastructure/source_config_store.py`

Se agrego proteccion de credenciales con Windows DPAPI:

- La contrasena de la base fuente no se guarda en texto plano.
- El archivo local queda en el arbol de estado del agente, bajo `config/source-database.json`.
- El secreto protegido depende del contexto Windows donde se ejecuto.

Ruta por defecto de estado:

```text
C:\ProgramData\Bapps\SyncAgent
```

### 4. Prueba de conexion fuente

Archivo:

- `agent/src/bapps_sync_agent/infrastructure/source_connection_tester.py`

Se agrego un probador de conexion para:

- MySQL via `PyMySQL`
- Firebird via `firebirdsql` (sin dependencia de `fbclient.dll`)

La prueba se ejecuta desde la GUI en un hilo de fondo para que la ventana no se congele.

### 5. Empaquetado portable

Archivo:

- `agent/scripts/build_portable.ps1`

El script:

- Instala el paquete local del agente en modo editable.
- Instala dependencias opcionales del portable.
- Ejecuta PyInstaller en modo `--windowed`.
- Incluye imports dinamicos necesarios para MySQL y Firebird.
- Genera la carpeta `agent/dist/BAPPS-Sync-Agent/`.

Comando documentado:

```powershell
cd C:\Sync\Valery\bapps-sync\agent
.\scripts\build_portable.ps1 -Python python
```

En esta maquina, `python` no esta en PATH durante esta sesion. La compilacion se hizo usando el entorno temporal:

```powershell
C:\tmp\bapps-sync-portable-venv\Scripts\python.exe
```

## Archivos modificados o agregados en esta etapa

- `agent/pyproject.toml`
- `agent/README.md`
- `agent/scripts/build_portable.ps1`
- `agent/src/bapps_sync_agent/main.py`
- `agent/src/bapps_sync_agent/ui/__init__.py`
- `agent/src/bapps_sync_agent/ui/app.py`
- `agent/src/bapps_sync_agent/ui_main.py`
- `agent/src/bapps_sync_agent/infrastructure/secret_protector.py`
- `agent/src/bapps_sync_agent/infrastructure/source_config_store.py`
- `agent/src/bapps_sync_agent/infrastructure/source_connection_tester.py`
- `agent/tests/test_source_config.py`

## Verificacion realizada

Se ejecutaron las pruebas automatizadas del agente con el Python del entorno de build:

```powershell
C:\tmp\bapps-sync-portable-venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado:

```text
Ran 9 tests in 0.074s
OK
```

Pruebas cubiertas:

- Persistencia de identidad y journal de comandos.
- Recuperacion de outbox.
- Backoff persistido del outbox.
- Estado de ejecuciones para recuperacion despues de crash.
- Lock de instancia unica.
- Persistencia de eventos del runner.
- Stop cooperativo con resultado interrumpido.
- Rechazo de motor fuente desconocido.
- Confirmacion de que la contrasena fuente no se escribe en texto plano.

Tambien se verifico que el portable quedo generado en disco.

## Lo que aun no esta probado

No se ha probado todavia:

- Conexion real a una base Firebird de Valery en otra maquina.
- Conexion real a una base MySQL fuente.
- Enrolamiento desde la GUI contra Laravel.
- Ejecucion de sincronizacion real leyendo tablas Valery/Profit.
- Instalacion en otra PC.
- Instalacion como servicio Windows.
- Firma del ejecutable o instalador formal.

## Limitaciones actuales importantes

La GUI actual es una primera entrega operativa para configuracion local de fuente, pero todavia no es el panel final completo del agente.

Limitaciones especificas:

- El Centro BAPPS se muestra desde la identidad local existente; aun falta el flujo visual de bootstrap/enrolamiento para que el agente nazca apuntando al Laravel central sin editarlo manualmente.
- El estado de MySQL BAPPS se muestra si llega dentro de la configuracion activa local como `bapps_mysql`; aun falta cerrar el contrato exacto de esa configuracion desde el panel central.
- La prueba de Firebird depende de que la maquina tenga conectividad real hacia el servidor Firebird; el portable ya no requiere `fbclient.dll`.
- El portable actual es carpeta autocontenida, no instalador MSI/EXE.

## Siguiente paso recomendado

El siguiente paso tecnico deberia ser cerrar el bootstrap del agente:

1. Definir un `bootstrap.json` o mecanismo equivalente generado por el panel central.
2. Hacer que la GUI lea ese bootstrap en modo solo lectura.
3. Agregar boton/flujo de enrolamiento visual contra Laravel.
4. Guardar la identidad resultante en el estado local del agente.
5. Recompilar el portable y probarlo en una segunda maquina con Firebird real.

Ese paso conecta la idea correcta del producto: el agente ya sabe a que BAPPS Sync pertenece; el usuario local solo configura la base que se va a leer.

## Corrección Firebird para portable - 2026-07-21

Durante la prueba contra Valery se detectó que la primera versión del portable usaba exclusivamente `firebird-driver`. Ese controlador carga el cliente nativo `fbclient.dll`. PyInstaller bloqueó la carga de una DLL externa aun cuando el usuario la seleccionó manualmente, con el mensaje `Most likely this dynlib/dll was not found when the application was frozen`.

Se cambió el agente para usar `firebirdsql` como controlador Firebird. Es un cliente de protocolo implementado en Python y no requiere `fbclient.dll`; por tanto se alinea con una de las estrategias de respaldo ya usadas por `C:\Sync\Valery\sync_clientes_valery\sync_clientes.py`.

Cambios realizados:

- `agent/pyproject.toml`: se reemplazó `firebird-driver` por `firebirdsql>=1.3.2` y `passlib>=1.7.4` en el extra `portable`.
- `agent/scripts/build_portable.ps1`: el empaquetado ahora incluye `firebirdsql` y ya no recolecta el paquete nativo `firebird`.
- `SourceConnectionTester`: prueba Firebird mediante `firebirdsql.connect()` y una consulta de solo lectura a `RDB$DATABASE`.
- GUI: se eliminó el selector de `fbclient.dll` y se agregó el campo local `Codificación Firebird`, con valor inicial `iso8859_1` para Valery.
- Persistencia: las configuraciones antiguas con `firebird_client_library` se cargan sin error; ese campo legado se descarta y no se vuelve a guardar.
- Pruebas: se agregaron casos para la conexión por `firebirdsql` y normalización de charset.

Verificación:

- Dependencia instalada en el entorno de build: `firebirdsql 1.4.6`.
- `python -m unittest discover -s tests -v`: 12 pruebas OK.
- Sintaxis de la interfaz verificada.
- Prueba de conexión de solo lectura desde el entorno de build: el controlador cargó sin requerir DLL y llegó a la etapa de red; esa máquina respondió `WinError 10061` en `localhost:3050`. Esto no valida todavía el Firebird de la PC objetivo, pero sí confirma que desapareció el bloqueo de `fbclient.dll`.
- Portable reconstruido en `agent/dist/BAPPS-Sync-Agent/`.

Corrección adicional después de probar el ejecutable en la PC Valery:

- `firebirdsql` sí estaba presente en el primer build, pero Firebird 2.5 selecciona `Legacy_Auth` y el cifrado DES de esa autenticación importa dinámicamente `passlib`.
- El mensaje genérico del agente ocultaba el nombre de la dependencia ausente; ahora informa exactamente qué módulo falta.
- El build incluye explícitamente `passlib.handlers.des_crypt`.
- Se agregó el argumento interno `--portable-self-test`, que carga `firebirdsql` y ejecuta el cifrado usado por `Legacy_Auth` dentro del ejecutable congelado.
- La autoprueba se ejecutó sobre `dist/BAPPS-Sync-Agent/BAPPS-Sync-Agent.exe` y finalizó con código `0`.

## Validación real Valery - 2026-07-22

La prueba pendiente contra una instalación real de Valery ya fue completada correctamente desde la PC objetivo. La GUI del portable obtuvo `Conexión correcta` con Firebird 2.5 usando:

- Host: `localhost`.
- Puerto: `3050`.
- Base: `C:\ValerySMB\Datos\VALERY3.MDF`.
- Usuario: `SYSDBA`.
- Codificación: `iso8859_1`.

El alias probado no estaba definido en el servidor Firebird; por ello debe utilizarse la ruta completa de la base para esta instalación. El siguiente pendiente ya no es la conectividad Firebird, sino el bootstrap, enrolamiento y heartbeat definidos en [PLAN_CONTINUACION_2026-07-22.md](PLAN_CONTINUACION_2026-07-22.md).

## Bootstrap y enrolamiento - 2026-07-22

Se implementó la primera vertical Centro BAPPS ↔ agente:

- El portable busca `bootstrap.json` junto a `BAPPS-Sync-Agent.exe`.
- El bootstrap contiene URL del centro, código de agente y token de enrolamiento de un solo uso; estos datos no se editan desde la GUI.
- Al primer inicio el agente se enrola automáticamente mediante `POST /api/v1/agent/enroll`.
- La identidad resultante se almacena con Windows DPAPI. Identidades locales antiguas en texto plano se migran al volver a cargarse.
- El runtime se inicia en segundo plano después del enrolamiento y usa el loop existente para descargar configuración y enviar heartbeats.
- La GUI actualiza automáticamente cada dos segundos el estado de conexión y el último heartbeat; también permite reintentar el enrolamiento si falla.
- El comando `bapps:demo-provision` acepta `--bootstrap-output` y `--base-url` para generar el artefacto de prueba personalizado.

## P2 MySQL BAPPS administrado por el centro - 2026-07-22

Implementado, pendiente de prueba contra un MySQL BAPPS real:

- Nueva migración de `agents`: destino MySQL cifrado y fecha de publicación.
- API de control: `PUT /api/v1/agents/{code}/bapps-mysql`; el cuerpo valida host, puerto, base, usuario y contraseña. La respuesta excluye la contraseña.
- Comando operativo `bapps:configure-mysql-target` para publicar el destino sin exponer la contraseña en la línea de comandos.
- El agente P2 (`0.2.0`) recibe contrato `1.1` con `targets.bapps_mysql`; los agentes P1 (`0.1.0`) continúan recibiendo contrato `1.0` sin el destino, por compatibilidad.
- En el agente, la contraseña recibida se almacena con Windows DPAPI. La GUI enseña solo servidor, base, usuario y fecha, y permite probar la conexión MySQL.
- El contrato está en [contracts/agent-config.v1.1.schema.json](contracts/agent-config.v1.1.schema.json).

Verificación completada el 2026-07-22:

- `php artisan migrate` aplicó la migración de destino MySQL correctamente.
- `AgentApiTest`: 6 pruebas y 29 aserciones correctas.
- `ConfigureAgentBappsMysqlTest`: 1 prueba y 6 aserciones correctas.
- El agente `AGT-VALERY-01` recibió la configuración `bappscloud.com:3306`, base `bapps_demo`, usuario `bapps_user_demo` por LAN.
- La prueba desde la PC Valery contra MySQL BAPPS devolvió `MySQL BAPPS: Conexión correcta.`

La contraseña no fue expuesta en consola ni en la GUI. P2 queda validado; el siguiente hito es P3, el sincronizador real `clientes_valery`.

## P3 sincronizador real `clientes_valery` - 2026-07-22

Implementado, pendiente de ejecución real controlada:

- `ClientesValerySynchronizer` queda registrado en el runtime del portable `0.3.0`.
- Solo ejecuta `SELECT * FROM CLIENTES ORDER BY CODIGO` sobre Firebird; no contiene sentencias de escritura contra Valery.
- Procesa lotes configurables, con valor inicial y máximo operativo de 200/1000; el perfil demo entrega 200.
- Crea/evoluciona `clientes_valery_sync` en MySQL BAPPS y aplica `INSERT ... ON DUPLICATE KEY UPDATE` con unicidad por `codigo`.
- Antes de cada lote consulta los códigos existentes para reportar inserciones y actualizaciones de la ejecución.
- Es cancelable entre lotes y utiliza los eventos `run_started` / `run_finished` persistidos en outbox por el runtime existente.
- El comando `bapps:queue-run AGT-VALERY-01 clientes_valery` publica la ejecución manual sin resetear el enrolamiento.

Verificación completada el 2026-07-22:

- `QueueAgentRunTest`: 1 prueba y 3 aserciones correctas.
- Se publicó una ejecución manual con `bapps:queue-run AGT-VALERY-01 clientes_valery`.
- La PC Valery con portable P3 reclamó el comando y sincronizó correctamente hacia MySQL BAPPS.

Evidencia de idempotencia, segunda ejecución 2026-07-22: la consulta `COUNT(*)` y `COUNT(DISTINCT codigo)` en `clientes_valery_sync` devolvió respectivamente `369` y `369`. No hubo duplicados por `codigo`.

P3 queda validado de extremo a extremo e idempotente para la muestra completa actual. Scheduler permanece deshabilitado hasta que se complete el bloque de operación/control P4.

## P4 scheduler local - 2026-07-22

Implementado en el portable `0.4.0`, pendiente de prueba temporizada en la PC Valery:

- Agenda únicamente sincronizadores con estado `enabled` y respeta `interval_seconds` (mínimo 60 segundos).
- Al iniciar o cambiar un intervalo, programa la primera ejecución para después del intervalo completo; no hay ejecución inmediata por instalación.
- Pausar/deshabilitar elimina la planificación futura. Un cambio de intervalo reinicia el contador.
- Si hay una ejecución manual o programada del mismo sync activa, no inicia un duplicado.
- 23 pruebas Python correctas, incluidas las transiciones de intervalo y pausa; autoprueba del portable correcta.

Validación real 2026-07-22: el panel registró una ejecución `schedule` exitosa de `clientes_valery`, duración 5.0 s, 369 filas leídas, 0 insertadas, 369 actualizadas y 0 fallidas. Scheduler e idempotencia validados.

Verificación realizada:

- 17 pruebas Python correctas, incluyendo bootstrap, cliente de enrolamiento, migración DPAPI y estado runtime.
- Portable reconstruido y autoprueba `--portable-self-test` correcta.

Pendiente de validación manual: ejecutar el comando Laravel en una consola con PHP disponible, generar un bootstrap con una URL alcanzable desde la PC Valery y comprobar el enrolamiento/heartbeat contra el servidor real.

## Servicio Windows P4 - 2026-07-22

Se implemento el host de servicio `BAPPS-Sync-Service.exe` para que el runtime no dependa de que la ventana Tkinter permanezca abierta. La GUI sigue siendo el panel local de configuracion, pruebas y estado.

- Nombre del servicio: `BAPPSyncAgent`.
- Directorio de estado compartido: `C:\ProgramData\Bapps\SyncAgent`.
- Instalacion: `agent/scripts/install_service.ps1` (PowerShell elevado).
- Desinstalacion: `agent/scripts/uninstall_service.ps1`; conserva estado y credenciales.
- Las credenciales se protegen con Windows DPAPI de maquina. La primera apertura de la GUI nueva migra automaticamente los secretos existentes protegidos por usuario.
- Durante la instalacion se restringen los permisos del directorio de estado al propietario, `SYSTEM` y administradores.
- La autoprueba del servicio `BAPPS-Sync-Service.exe --portable-self-test` finalizo correctamente y la suite Python tiene 23 pruebas correctas.

Los dos artefactos finales fueron generados desde un Python aislado que incluye Tkinter y se empaquetaron en `agent/release/BAPPS-Sync-Agent-0.4.1-windows-x64.zip`. El ZIP fue revisado: contiene GUI, servicio, instalador y guia. Esta version corrige el orden de argumentos requerido para registrar el servicio y falla de forma explicita si la instalacion no se completa. Antes de instalar en Valery se debe abrir una vez la GUI actualizada; falta la prueba administrativa real de instalar, detener/iniciar y observar heartbeat con la GUI cerrada.

## Actualización P4 — instalador gráfico 0.4.2 (2026-07-23)

Se sustituyó el procedimiento de distribución para usuario final por un único
asistente Windows:

- Artefacto generado: `agent/release/BAPPS-Sync-Setup-0.4.2.exe`.
- Formato: instalador gráfico NSIS, con elevación UAC solo porque Windows exige
  privilegios administrativos para registrar el servicio.
- Instala la GUI en `C:\Program Files\BAPPS Sync Agent`, instala el host de
  servicio separado y crea accesos directos/desinstalador.
- El asistente ejecuta internamente la preparación de estado y las operaciones
  nativas de alta/inicio de `BAPPSyncAgent`; el usuario no debe abrir
  PowerShell ni ejecutar scripts.
- Si el agente no está enrolado, el asistente deja la GUI instalada y explica
  que debe enrolarse antes de poder activar el servicio. No registra un
  servicio incompleto.
- La actualización conserva `C:\ProgramData\Bapps\SyncAgent`; no requiere
  reenrolar ni reconfigurar Firebird o MySQL BAPPS.

Corrección técnica incluida: el ejecutable congelado del servicio detecta ahora
la invocación sin argumentos del Service Control Manager y se registra en su
dispatcher. Esta era la causa del timeout 1053 observado al iniciar la versión
0.4.1: el servicio quedaba registrado, pero no entraba al dispatcher de
Windows.

Verificación de esta entrega:

- Reconstrucción de GUI y servicio con PyInstaller completada.
- `BAPPS-Sync-Service.exe --portable-self-test` correcto.
- Suite Python: 23 pruebas correctas.
- Compilación NSIS correcta; tamaño de `BAPPS-Sync-Setup-0.4.2.exe`:
  16,261,379 bytes.
- SHA-256: `49D68429779F395ED0B54B4B932D49734395D9146FEA387BF8F737711FB4610C`.

Pendiente de cierre P4: ejecutar el `Setup.exe` 0.4.2 en la PC Valery,
aceptar UAC, cerrar la GUI y confirmar desde el Centro BAPPS que siguen llegando
heartbeats (y una ejecución programada) con el servicio en ejecución.

## F5 y servicio validado — 2026-07-23

La PC Valery confirmó que `AGT-VALERY-01` mantiene heartbeat cada 30 segundos
con la GUI cerrada. Por tanto el servicio Windows es operativo y Tkinter no es
requisito de ejecución.

Se implementó `LocalSyncLogRepository` para registrar resultados en el MySQL
BAPPS que recibe el agente. Crea `sync_success` y `sync_errors` si faltan;
éxitos y fallos se registran allí, pero una indisponibilidad de esa bitácora no
modifica el desenlace ni la entrega central por outbox. Las 28 pruebas del
agente pasaron.

Se generó `agent/release/BAPPS-Sync-Setup-0.5.0.exe` (16,395,299 bytes;
SHA-256 `DF103856EE5BC29503DEA1602A590BBD410D6B76BA16FA12F97D874B33FF926F`).
Está preparado para la siguiente actualización, no como sustitución automática
de la instalación estable. Antes de actualizar se debe hacer una prueba limpia
del asistente y luego validar una ejecución real con su fila en `sync_success`.

## Corrección de instalación 0.4.3 (2026-07-23)

La primera ejecución de `Setup 0.4.2` en Valery detectó una ACL heredada de
una instalación técnica previa: el instalador elevado no podía abrir
`C:\ProgramData\Bapps\SyncAgent\config\agent-identity.json`, aunque el
agente ya estuviera enrolado. No se expuso ninguna credencial ni se alteró el
enrolamiento.

Se generó `agent/release/BAPPS-Sync-Setup-0.4.3.exe`. Antes de preparar el
servicio, repara de forma administrativa los permisos del directorio de estado
para `SYSTEM` y Administradores; conserva los archivos existentes y los
secretos siguen protegidos por DPAPI de máquina. También mantiene la
detención segura del servicio existente antes de actualizar binarios.

Validación local: GUI y servicio recompilados, 23 pruebas Python y
autoprueba del servicio correctas; NSIS compiló sin advertencias.

- Tamaño: 16,262,558 bytes.
- SHA-256: `15D42609772E6BDB7DB56AEEB2E44FD1C91B09F12D079E035AD135C8354EA653`.

## Corrección 0.4.4: instalación sin lectura elevada de identidad (2026-07-23)

La 0.4.3 todavía intentaba abrir `agent-identity.json` desde el proceso
elevado del instalador. En la PC Valery una ACL explícita heredada lo impidió.
Para eliminar esa dependencia incorrecta, `BAPPS-Sync-Setup-0.4.4.exe` ya no
lee ni migra la identidad desde el instalador: restaura la ACL del directorio
de estado para `SYSTEM` y Administradores, registra el servicio y lo inicia.
El servicio es quien utiliza la identidad cifrada con DPAPI de máquina bajo su
cuenta `SYSTEM`.

Esto preserva los secretos y evita que el instalador tenga que acceder al
contenido de la identidad. El estado existente de Valery ya fue creado por la
GUI actual y usa el alcance DPAPI de máquina.

- Artefacto: `agent/release/BAPPS-Sync-Setup-0.4.4.exe`.
- Tamaño: 16,262,488 bytes.
- SHA-256: `3A8A7F1FCD1EC308907F51F105ADEAF0BBB4B71BE2DB2134BEAEC24D2A70AA04`.
- Verificación: 23 pruebas Python, autoprueba del servicio y compilación NSIS
  sin advertencias correctas.

## Corrección 0.4.5: ACL nativa de Windows (2026-07-23)

La 0.4.4 confirmó que la ACL heredada también bloqueaba a `SYSTEM`. Se reemplazó
la reparación basada en comandos externos por `state_permissions.py`, incluido
en el agente: con privilegios administrativos toma posesión de cada archivo y
carpeta del estado y asigna una DACL protegida explícita solo a `SYSTEM` y al
grupo Administradores. Luego el instalador valida la identidad y registra el
servicio.

- Artefacto: `agent/release/BAPPS-Sync-Setup-0.4.5.exe`.
- Tamaño: 16,383,774 bytes.
- SHA-256: `BCCEBB384751662103D62A3D945292F48C321309DFB5468D7CD3AB0AFE18243D`.
- Verificación: importación del módulo de seguridad, 23 pruebas Python,
  autoprueba del servicio y NSIS sin advertencias correctas.

## Corrección 0.4.6: actualización con servicio activo (2026-07-23)

La prueba de 0.4.5 logró iniciar el servicio, pero la actualización posterior
intentó copiar `win32servicemanager.pyd` mientras dicho servicio aún conservaba
la DLL cargada. El instalador 0.4.6 primero solicita la parada ordenada y, si
Windows todavía mantiene el host del servicio, finaliza exclusivamente el
proceso asociado a `BAPPSyncAgent` antes de extraer los binarios nuevos. Una
ejecución activa se recupera como interrumpida mediante el estado durable ya
existente.

- Artefacto: `agent/release/BAPPS-Sync-Setup-0.4.6.exe`.
- Tamaño: 16,381,105 bytes.
- SHA-256: `34047A9F1CD0608E8239E42361390DF9105C46D67E69968FA00FF0CA3D289BBC`.
- Verificación: 23 pruebas Python, autoprueba del servicio y NSIS sin
  advertencias correctas.

## Corrección 0.4.8: desinstalación visible en Windows (2026-07-23)

El instalador anterior generaba `Uninstall.exe`, pero no registraba la entrada
estándar de Windows en `...\CurrentVersion\Uninstall`; por eso BAPPS Sync
Agent no aparecía en Programas y características. El Setup 0.4.8 registra
nombre, versión, editor, ubicación e instrucción de desinstalación, y retira
esa entrada durante el uninstall.

- Artefacto: `agent/release/BAPPS-Sync-Setup-0.4.8.exe`.
- Tamaño: 16,385,672 bytes.
- SHA-256: `B4475E1BB792199A19B4CC3D9ED62B1177AF261452D8385CF82D548E1AF20D90`.
- Compilación NSIS sin advertencias.

## Corrección 0.4.7: liberación exacta del host PyInstaller (2026-07-23)

La actualización 0.4.6 mostró que Windows no clasificaba el host congelado en
el filtro de servicio de `taskkill`, por lo que mantenía cargada
`win32servicemanager.pyd`. El instalador 0.4.7 conserva la parada ordenada y,
si hace falta, termina por nombre de imagen el único host de BAPPS:
`BAPPS-Sync-Service.exe`, espera dos segundos y solo entonces extrae archivos.

- Artefacto: `agent/release/BAPPS-Sync-Setup-0.4.7.exe`.
- Tamaño: 16,385,478 bytes.
- SHA-256: `D9359F52F1F131D4489745E13880E6B92DD8876088D61BA1E1E419709F1CF770`.
- Verificación: 23 pruebas Python, autoprueba del servicio y NSIS sin
  advertencias correctas.
