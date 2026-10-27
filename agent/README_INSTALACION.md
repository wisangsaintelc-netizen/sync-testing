# BAPPS Sync Agent 0.7.10 — instalación para Windows

El artefacto principal es:

```text
agent\release\BAPPS-Sync-Setup-0.7.10.exe
```

No requiere Python, PHP ni PowerShell instalados en la PC cliente. El instalador
incluye el panel, el servicio Windows, los controladores Python de Firebird,
SQL Server y MySQL, y la verificación Ed25519.

## Estado del artefacto

0.7.10 incorpora las filas auxiliares de cabecera que Valery necesita para reconocer un PRS creado por el agente: `VENTAS_AD`, `VENTAS_ESTADOS` y `VENTAS_EXT`. También empaqueta Tcl/Tk de forma obligatoria y valida el ejecutable portable antes de publicar el instalador. Además añade diagnóstico seguro de sincronizaciones: ante un fallo inesperado envía el
tipo de excepción y el detalle técnico útil, ocultando contraseñas, tokens,
secretos y credenciales en URL. Cada consulta de preview lee como máximo dos
filas para habilitar Siguiente y nunca recibe SQL ni entrega credenciales.
Conserva las reparaciones de confianza y estado de 0.6.1/0.6.2. El ejecutable
aún no tiene firma Authenticode comercial; su integridad debe comprobarse con
el SHA-256 documentado.

## Qué instala

- El panel local BAPPS Sync Agent para enrolamiento, estado y perfiles fuente.
- El servicio `BAPPSyncAgent`, que ejecuta heartbeat, comandos, agenda,
  sincronizaciones y reintentos con la ventana cerrada.
- El motor de recetas declarativas firmadas para lecturas SQL Server/Profit y
  Firebird/Valery.
- El escritor empaquetado `valery_prs_writer_v1`, que reclama un pedido por vez
  y publica `VENTAS`, `VENTAS_DETALLES` y `VENTAS_DETALLES_EXT` en una sola
  transacción Firebird, sin recibir SQL ni código desde el Centro.
- Protección DPAPI del token privado de pedidos, además de las credenciales
  locales ya protegidas.
- El comando seguro `inspect_source_table` para seleccionar campos desde el
  panel mediante un agente online.
- Un desinstalador y accesos directos del menú Inicio.

El estado y las credenciales locales permanecen protegidos bajo:

```text
C:\ProgramData\Bapps\SyncAgent
```

El desinstalador conserva ese estado para permitir actualizaciones. Por ello,
un piloto separado debe usar otra PC o VM y una identidad nueva; no se deben
ejecutar dos agentes contra el mismo directorio de estado.

## Instalación del piloto

1. Verifique el SHA-256 del instalador.
2. Prepare un `bootstrap.json` para una identidad distinta, por ejemplo
   `AGT-VALERY-PILOTO`.
3. Ejecute el instalador con doble clic y acepte UAC.
4. Abra el panel y complete el enrolamiento.
5. Cree y pruebe el perfil fuente `valery_piloto` con un usuario Firebird de
   solo lectura.
6. Confirme que el Centro entrega la configuración MySQL piloto y que la prueba
   de conexión funciona.
7. Cierre el panel y confirme que el servicio mantiene heartbeat.

La clave privada de firma nunca se copia a la PC cliente. Este Setup incorpora
únicamente la clave pública derivada por el Centro. Si la identidad ya tiene
otra clave, el instalador aborta; nunca cambia la confianza silenciosamente.

## Actualización

El instalador detiene el servicio, reemplaza los binarios, repara permisos y
lo inicia nuevamente, conservando identidad y perfiles. 0.7.10 actualiza
directamente instalaciones 0.6.x, habilita la inspección centralizada paginada
y mejora el detalle seguro de errores de ejecución. También corrige una marca
interna que podía invalidar, al releerse, una receta firmada con destino MySQL.
También elimina los respaldos temporales internos de publicaciones anteriores.

Un `run_now` aceptado se marca como **Enviado** en el historial de comandos:
esa marca confirma que el agente recibió la orden. El estado real (Success,
Failed o Interrupted) siempre se consulta en **Ejecuciones**.

## Desinstalación

Use **BAPPS Sync Agent > Desinstalar** o Aplicaciones instaladas de Windows. El
asistente elimina aplicación y servicio, pero conserva el estado local. Su
eliminación deliberada es una operación separada.

Los scripts `install_service.ps1` y `uninstall_service.ps1` quedan solo para
diagnóstico técnico; no forman parte del procedimiento normal.
