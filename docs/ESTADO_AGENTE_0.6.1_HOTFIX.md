# Estado del agente 0.6.1 — hotfix de confianza y backoff

Fecha: 2026-07-29.

## Incidente observado

Después de instalar 0.6.0 en la PC Valery, el agente conservó correctamente la
identidad 0.5.4, pero esa identidad no contenía
`config_signing_public_key`. El agente rechazó la configuración firmada y
mostró:

```text
Sin conexión: El agente no tiene la clave pública para verificar la configuración.
```

Además, el fallo mantenía activo `refresh_config` y generaba una solicitud
`GET /api/v1/agent/config` aproximadamente cada segundo.

## Corrección 0.6.1

- El Centro deriva la clave pública Ed25519 desde la privada almacenada en
  `.env`; la privada nunca se exporta.
- `bapps:export-agent-signing-trust` genera un JSON que contiene únicamente
  algoritmo, `key_id` y clave pública.
- El Setup 0.6.1 incorpora ese paquete y agrega la clave a la identidad
  heredada durante la actualización.
- Se conserva el token enrolado, el código del agente, la URL, los perfiles
  Firebird y la configuración MySQL protegida con DPAPI.
- Una clave ya fijada solo acepta una repetición idéntica. Una clave distinta
  aborta y exige un procedimiento explícito de rotación.
- El agente conserva un llavero. Una rotación planificada agrega la próxima
  clave dentro de una configuración firmada por una clave ya confiable; después
  el Centro puede cambiar de firmante sin reinstalar agentes.
- Una transición no puede redefinir un `key_id`, retirar la misma clave que la
  firma ni dejar el llavero vacío.
- Los fallos al refrescar configuración usan backoff exponencial aproximado:
  5, 10, 20, 40, 80, 160 y hasta 300 segundos, con jitter.

## Artefacto

| Archivo | Tamaño | SHA-256 |
|---|---:|---|
| `agent\release\BAPPS-Sync-Setup-0.6.1.exe` | 20.514.172 bytes | `9058495F6F77DD065BA1E51DDEFEDAD3B602262BB477D1FA0AC5D865D71ED837` |

El ejecutable todavía no tiene firma Authenticode comercial.

## Validaciones

- Agente: 76 pruebas correctas.
- Laravel: 41 pruebas, 235 aserciones.
- Pint y sintaxis del comando de exportación: correctos.
- Paquete público: Ed25519, 32 bytes, `recipe-v1`, sin clave privada.
- Binario real: importó la confianza en una identidad heredada de prueba y
  preservó exactamente el token.
- Pruebas de rotación: segunda clave aceptada, transición sin reinstalación,
  retiro firmado por la nueva y bloqueo del autorretiro.
- Autopruebas del panel y servicio: correctas.

## Aplicación en la PC Valery

1. Copiar y ejecutar `BAPPS-Sync-Setup-0.6.1.exe`.
2. No desinstalar 0.6.0 y no borrar `C:\ProgramData\Bapps\SyncAgent`.
3. El instalador detiene el servicio, fija la clave pública, actualiza los
   binarios y vuelve a iniciar el servicio.
4. Abrir el panel y confirmar `Estado: Conectado`.
5. En la consola del Centro confirmar que `/agent/config` deja de repetirse
   cada segundo; heartbeat y `commands/claim` continuarán con sus intervalos
   normales.

## Gate de transporte

El Centro mostrado por el agente usa actualmente
`http://192.168.0.116:8000`. Esto sirve solo para el laboratorio LAN
controlado. Antes de producción es obligatorio usar HTTPS válido; de otro modo
el token del agente y las configuraciones no tienen confidencialidad ni
autenticación de transporte.

## Rotación planificada sin reinstalación

1. Mantener `recipe-v1` como activa.
2. Configurar temporalmente en el Centro:

   ```text
   BAPPS_SYNC_RECIPE_SIGNING_NEXT_PRIVATE_KEY=<privada-v2-base64>
   BAPPS_SYNC_RECIPE_SIGNING_NEXT_KEY_ID=recipe-v2
   ```

3. El Centro sigue firmando con v1 y distribuye la pública v2 dentro del
   contenido firmado.
4. Confirmar que los agentes recibieron v2.
5. Promover v2 a las variables activas y limpiar las variables `NEXT_*`.

La privada v2 tampoco se entrega a los agentes. Una emergencia en la que v1
ya no sea confiable requiere un canal externo seguro; una clave comprometida
no puede autorizar su propia sustitución.
