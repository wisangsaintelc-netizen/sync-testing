# Guía de prueba vertical (desarrollo)

Esta guía prepara datos locales reproducibles y comprueba el recorrido real del API Laravel: enrolamiento, `heartbeat`, configuración y reclamación de comandos. No ejecuta una conexión Firebird real; el adaptador productivo de `clientes_valery` sigue pendiente.

## 1. Preparar el entorno

Desde `C:\Sync\Valery\bapps-sync`, asegúrate de tener las migraciones aplicadas y prepara los datos demo:

```powershell
php artisan migrate
php artisan bapps:demo-provision --with-command
```

El comando crea o actualiza, exclusivamente para desarrollo:

- Operador: `operator@bapps.test` / `bapps-demo-password`.
- Cliente: `Cliente de demostración BAPPS`.
- Agente: `AGT-DEMO`.
- Token de enrolamiento: `demo-enrollment-token-123456`.
- Sincronización habilitada: `clientes_valery` cada 900 segundos.
- Comando pendiente opcional: `CMD-DEMO-RUN-NOW`.

Al volver a ejecutar el comando, el token anterior del agente se sustituye por el token de enrolamiento indicado. Nunca lo uses fuera de un entorno local.

Inicia el centro en otra consola:

```powershell
php artisan serve
```

Los ejemplos siguientes asumen `http://127.0.0.1:8000`.

## 2. Enrolar el agente

Ejecuta este bloque en PowerShell. Guarda el token devuelto: es distinto del token de enrolamiento y es el que debe usar el agente después de enrolarse.

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$agentCode = 'AGT-DEMO'
$enrollmentToken = 'demo-enrollment-token-123456'

$enrollment = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/agent/enroll" -ContentType 'application/json' -Body (@{
    agent_code = $agentCode
    enrollment_token = $enrollmentToken
    machine_name = $env:COMPUTERNAME
    agent_version = '1.0.0-dev'
    os = 'Windows'
} | ConvertTo-Json)

$agentToken = $enrollment.agent_token
$agentToken
```

Para repetir el enrolamiento, ejecuta otra vez `bapps:demo-provision`; eso restaura el token de enrolamiento.

## 3. Comprobar conexión y configuración

```powershell
$headers = @{ Authorization = "Bearer $agentToken"; 'X-Agent-Code' = $agentCode }

Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/agent/heartbeat" -Headers $headers -ContentType 'application/json' -Body (@{
    agent_code = $agentCode
    machine_name = $env:COMPUTERNAME
    agent_version = '1.0.0-dev'
    config_version = $enrollment.config_version
    status = 'online'
    running_runs = @()
    outbox = @{ pending_count = 0; pending_bytes = 0 }
} | ConvertTo-Json)

Invoke-RestMethod -Method Get -Uri "$baseUrl/api/v1/agent/config" -Headers $headers
```

El `heartbeat` debe devolver `acknowledged: true`; la configuración debe contener `syncs[0].code = clientes_valery`.

## 4. Reclamar el comando de prueba

Si preparaste el entorno con `--with-command`, comprueba el sondeo del agente:

```powershell
$claim = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/agent/commands/claim" -Headers $headers -ContentType 'application/json' -Body (@{
    agent_code = $agentCode
    max_commands = 5
    known_command_ids = @()
} | ConvertTo-Json)

$claim
```

La respuesta debe incluir `CMD-DEMO-RUN-NOW`, de tipo `run_now`, y su estado pasa a `claimed`. Esta prueba valida el contrato y la entrega; el agente Python aún no registra un sincronizador Firebird real, por lo que no intenta sincronizar datos de Valery.

## 5. Verificaciones automatizadas

```powershell
php artisan test
$env:PYTHONPATH = 'agent/src'
& 'C:\Users\USUARIO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s agent/tests -v
```

La primera orden verifica Laravel, incluido el aprovisionador demo. La segunda verifica el núcleo Python F1-F2 (estado, outbox, recuperación y ejecución cooperativa).

## 6. Validación de la fuente Valery con el portable

Esta validación no enrola todavía el agente; confirma solamente que la fuente Firebird local está lista para la siguiente vertical.

1. Copia la carpeta completa `agent/dist/BAPPS-Sync-Agent/` a la PC de Valery.
2. Abre `BAPPS-Sync-Agent.exe`.
3. Configura la fuente con `firebird`, `localhost`, puerto `3050`, usuario `SYSDBA`, charset `iso8859_1` y la ruta completa `C:\ValerySMB\Datos\VALERY3.MDF`.
4. Pulsa **Probar conexión** y luego **Guardar**.

Resultado ya comprobado el 2026-07-22: `Conexión correcta`. No se debe usar `valery_sb` como alias en esta instalación, porque Firebird lo interpreta como una ruta inexistente.

## 7. Enrolar el portable desde la PC Valery

En la PC que ejecuta Laravel, inicia el servidor de forma alcanzable desde la PC Valery. Para una prueba LAN, sustituye `192.168.1.50` por la IP real del servidor:

```powershell
php artisan serve --host=0.0.0.0 --port=8000
php artisan bapps:demo-provision --agent-code=AGT-VALERY-01 --enrollment-token=valery-enrollment-token-2026 --bootstrap-output='C:\Sync\Valery\bapps-sync\agent\dist\BAPPS-Sync-Agent\bootstrap.json' --base-url='http://192.168.1.50:8000'
```

Después copia la carpeta completa `agent/dist/BAPPS-Sync-Agent/` a la PC Valery y abre el ejecutable. El agente debe mostrar el código `AGT-VALERY-01`, enrolarse automáticamente y cambiar a **Conectado** tras el primer heartbeat.

Para verificarlo desde Laravel, consulta la lista de agentes autenticándote en la API de control o revisa el registro `agents.last_seen_at`. Si el enrolamiento falla, confirma que la IP/puerto del `base-url` es alcanzable desde la PC Valery; `localhost` no apunta al servidor Laravel cuando se usa desde otra máquina.

## 8. Publicar y probar MySQL BAPPS para un agente (P2)

1. En la PC del Centro BAPPS, actualiza la estructura de datos:

```powershell
php artisan migrate
```

2. Sustituye la carpeta portable de la PC Valery por la versión P2 de `agent/dist/BAPPS-Sync-Agent/`. El estado del agente permanece en `C:\ProgramData\Bapps\SyncAgent`, por lo que no es necesario enrolarlo de nuevo.
3. Publica el destino para el agente. La contraseña se solicita oculta y no se imprime ni queda en el historial de la consola:

```powershell
php artisan bapps:configure-mysql-target AGT-VALERY-01 --host=IP_O_HOST_MYSQL --port=3306 --database=NOMBRE_BD --username=USUARIO_MYSQL
```

4. Cierra y abre el portable. Tras el siguiente heartbeat/refresco, el bloque **MySQL BAPPS** debe mostrar servidor, base, usuario y fecha de recepción. Pulsa **Probar MySQL BAPPS**.

La conexión debe realizarse desde la PC Valery hacia el servidor MySQL destino; confirma que el firewall, la cuenta MySQL y sus permisos permiten esa conexión. La contraseña no se muestra en la interfaz ni se guarda en claro: Laravel la cifra en el Centro BAPPS y el agente la protege con Windows DPAPI.

## 9. Primera sincronización real `clientes_valery` (P3)

1. Sustituye el portable de la PC Valery por la versión P3. Conserva el estado existente en `C:\ProgramData\Bapps\SyncAgent`; no debes enrolar nuevamente.
2. Abre el agente y confirma que siguen correctas las pruebas de Firebird y MySQL BAPPS.
3. Solo cuando el portable P3 esté abierto y **Conectado**, publica una ejecución manual desde el Centro BAPPS:

```powershell
php artisan bapps:queue-run AGT-VALERY-01 clientes_valery
```

4. Espera unos segundos. El agente toma el comando, lee exclusivamente `CLIENTES` de Firebird en lotes de 200 y crea/actualiza `clientes_valery_sync` en MySQL por la clave `codigo`.
5. Verifica en MySQL BAPPS el conteo y una muestra de registros. Repite el comando: los mismos códigos deben actualizarse sin duplicarse.

No publiques el comando mientras siga abierto un portable P2: esa versión no contiene el sincronizador y lo marcaría como no registrado.

## 10. Scheduler local por intervalo (P4)

El portable `0.4.0` agenda cada sincronizador con estado `enabled` usando su `interval_seconds` recibido del Centro. La primera ejecución automática se programa **después** de recibir la configuración y de transcurrir el intervalo; no se ejecuta inmediatamente al abrir el agente.

Para una prueba corta:

1. En el panel real ve a **Agentes → Asignación**, selecciona `AGT-VALERY-01`, conserva `enabled` y establece temporalmente el intervalo en `60` segundos. Guarda.
2. Cierra el portable P3, reemplázalo por el portable `0.4.0` y ábrelo. Confirma que aparece conectado.
3. Espera hasta 90 segundos y revisa **Ejecuciones**: debe aparecer una ejecución con trigger `schedule`.
4. Al validar, restaura el intervalo a `900` segundos desde la misma pantalla.

Si una ejecución manual está activa, el scheduler no inicia una segunda copia del mismo sync; la intentará de nuevo en el siguiente intervalo. Pausar o deshabilitar el sync cancela su planificación futura, sin detener una ejecución ya iniciada.

## 11. Servicio Windows (cierre P4)

Esta prueba sustituye el runtime que hoy inicia la GUI por un servicio Windows permanente. La GUI se conserva como panel local; puede cerrarse despues de instalar el servicio.

Antes de instalar:

1. Copia y extrae `agent/release/BAPPS-Sync-Agent-0.4.1-windows-x64.zip` en la PC Valery. No uses el ZIP 0.4.0: el ZIP 0.4.1 corrige el registro del servicio. Contiene `BAPPS-Sync-Agent`, `BAPPS-Sync-Service`, los scripts y la guia.
2. Si se genera una version nueva, usa un Python Windows que tenga Tkinter para producir ambos artefactos.
3. Abre una vez la GUI nueva con el usuario que ya usa el agente, espera a que cargue Firebird/MySQL BAPPS y confirma que esta conectado. Esto migra en forma automatica las credenciales anteriores a DPAPI de maquina, requerida por el servicio.

Luego, en PowerShell **como Administrador**:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\ruta\del\proyecto\agent
.\scripts\install_service.ps1
Get-Service BAPPSyncAgent
```

Debe aparecer con estado `Running`. Cierra la GUI, espera al siguiente heartbeat (hasta 30 segundos) y confirma desde **Agentes** que `AGT-VALERY-01` sigue online. Para validar scheduler, conserva un sync `enabled`, espera su intervalo y revisa **Ejecuciones**.

Para detener y retirar el servicio sin borrar la configuracion local:

```powershell
cd C:\ruta\del\proyecto\agent
.\scripts\uninstall_service.ps1
```

El instalador actual es un script administrativo reproducible, no un MSI/EXE firmado. La firma y el instalador unico son el siguiente endurecimiento de distribucion.
