# Estado del agente 0.6.2 — firma HTTP y estado estable

Fecha: 2026-07-29

## Incidente observado

`AGT-VALERY-01` alternaba visualmente entre `Conectado` y
`Sin conexión: La firma de configuración no es válida`.

El botón `Probar conexión` no intervenía en ese estado: comprueba la base de
datos fuente local. La alternancia ocurría porque:

1. el heartbeat exitoso marcaba el agente como conectado;
2. `/api/v1/agent/config` entregaba una configuración cuya firma no validaba;
3. el agente mostraba el rechazo;
4. el siguiente heartbeat borraba visualmente ese rechazo.

No era una autorreparación ni una caída de red.

## Causa raíz

La API construía `syncs` como una `Illuminate\Support\Collection`. El firmador
canónico no descendía dentro de objetos `JsonSerializable`, por lo que firmaba
el orden interno de los campos. Después, `JsonResponse` convertía la colección
en un arreglo JSON. El agente verificaba correctamente los bytes recibidos,
que ya no coincidían con los bytes firmados.

Se comprobó de forma controlada que:

- la clave pública derivada por la API y la incorporada en el instalador eran
  idénticas;
- PHP y Python producían el mismo JSON canónico a partir de la respuesta;
- el único bloque modificado durante la respuesta era `syncs`;
- después de la corrección, el verificador real del agente devuelve
  `VERIFY_OK:recipe-v1`.

## Correcciones

Centro:

- `syncs` se convierte explícitamente a arreglo antes de firmar;
- el firmador normaliza recursivamente cualquier `JsonSerializable`;
- se agregó una prueba de regresión que verifica la firma después del viaje
  completo por `JsonResponse`.

Agente 0.6.2:

- heartbeat y validez de configuración son estados separados;
- un heartbeat exitoso ya no borra un rechazo de firma;
- el estado degradado muestra `Centro accesible; configuración rechazada: …`;
- una configuración válida limpia el error de seguridad.

## Validación

- Laravel: 42/42 pruebas, 236 aserciones.
- Agente: 78/78 pruebas.
- Pint sobre los archivos PHP modificados: correcto.
- Verificación PHP → respuesta HTTP → Python/Ed25519: correcta.

El chequeo Pint global conserva un hallazgo preexistente y ajeno en
`routes/api.php` (`ordered_imports`); no se modificó incidentalmente.

## Instalador

| Artefacto | Tamaño | SHA-256 | Authenticode |
|---|---:|---|---|
| `agent/release/BAPPS-Sync-Setup-0.6.2.exe` | 20.476.674 bytes | `5BBC6DF19F8E54B17EF060BE12DC7B5011E314DA97956B791AFE4CC49BAB02F2` | No firmado |

La ausencia de firma Authenticode continúa siendo un gate de producción.

## Continuación inmediata

1. Sin reinstalar todavía, observar el siguiente `/agent/config`: la
   corrección del Centro debe hacer que 0.6.1 acepte la firma.
2. Instalar 0.6.2 sobre 0.6.1 para incorporar el modelo de estado no
   oscilante. El instalador conserva identidad, token DPAPI, perfiles y
   configuración local.
3. Confirmar `Conectado`, versión 0.6.2 en el Centro y ausencia de nuevos
   rechazos durante al menos dos ciclos de configuración/heartbeat.
4. Continuar con el piloto funcional Valery y el plan de resiliencia.
