# Valery PRS writer v1

## Alcance

`valery_prs_writer_v1` forma parte del agente 0.7.10. Consume exclusivamente la
API privada de pedidos, conserva la fecha original del pedido y escribe un
presupuesto `PRS` con vencimiento fijo de 15 días. No usa `tpedidos`,
`treng_ped`, SQL descargado, triggers ni movimientos de inventario.

## Despliegue

1. En la app de pedidos, ejecutar migraciones.
2. Crear o rotar una credencial con:
   `php artisan bapps-sync:order-agent AGT-VALERY-01`.
3. Crear en el catálogo un sincronizador de dirección **Escritura** y motor
   empaquetado **Valery PRS writer v1**, con agente mínimo 0.7.0.
4. Asignarlo al agente indicando perfil Firebird, depósito, estación, usuario,
   servidor, URL privada y el token mostrado una sola vez.
5. Instalar `BAPPS-Sync-Setup-0.7.10.exe` y actualizar configuración.
6. Ejecutar primero con una copia de Valery y validar un pedido de un renglón,
   uno de varios renglones y uno exento.

Artefacto vigente generado el 2026-07-31:

- `agent/release/BAPPS-Sync-Setup-0.7.10.exe`
- 20.752.719 bytes
- SHA-256 `2223C91B9E827088C458B5FB6341D13900852899D0B98750BC621D0A16E36715`

El token se almacena cifrado en el Centro y con Windows DPAPI en el agente.
Para revocarlo:
`php artisan bapps-sync:order-agent AGT-VALERY-01 --revoke`.

## Contrato

- `claim` entrega como máximo un pedido y un lease temporal.
- `complete` solo se acepta con el lease vigente y registra `CORRELATIVO`,
  `DOCUMENTO`, factor y fecha de escritura.
- `fail` distingue reintentos de fallos definitivos y aplica backoff.
- `orders.sync` permanece en 0 hasta el commit confirmado; después pasa a 1 y
  `sync_fact_num` recibe `VENTAS.DOCUMENTO`.
- `ORDEN_DE_COMPRA=orders.code` es la clave idempotente ante pérdida del ACK.
- En v1 cualquier descuento distinto de cero es rechazado.

## Blindajes

La receta Ed25519 solo contiene identificadores y opciones controladas. El
agente valida tablas y maestros, moneda 02, factor positivo y esquema antes de
insertar. Todos los cálculos monetarios usan decimal y redondeo comercial. El
commit de cabecera, detalles y textos es único; las colisiones de numeración
reintentan la transacción completa hasta cinco veces.

## Estado de implementación a 2026-08-03

### Flujo implementado

1. El agente reclama un solo `order_sync_job` mediante la API privada de pedidos y toma un lease temporal.
2. Antes de escribir, verifica receta firmada, perfil Firebird, columnas e índices mínimos, moneda `02`, factor positivo, cliente, vendedor y productos facturables.
3. `ORDEN_DE_COMPRA=orders.code` es la clave de idempotencia. Si ya existe un `PRS` con ese valor, confirma el job sin duplicarlo.
4. Reserva el siguiente `CORRELATIVO`, documento PRS y `NUMERO_LINEA`. Los documentos PRS vacíos, nulos o no numéricos no reinician la serie.
5. En una sola transacción Firebird inserta `VENTAS`, `VENTAS_AD`, `VENTAS_ESTADOS`, `VENTAS_EXT`, `VENTAS_DETALLES` y, cuando aplica, `VENTAS_DETALLES_EXT` con condición de pago, destino y observación en fragmentos de hasta 100 caracteres.
6. El encabezado usa moneda principal `01`; los renglones conservan la cotización USD en moneda `02` con su factor vigente. La vigencia queda fija en 15 días desde la creación original del pedido.
7. Normaliza los acumulados de cabecera después de insertar detalles para evitar la duplicación automática observada en Valery.
8. Valida renglones, cantidades, neto, total y totales principales de `VENTAS` antes del commit y antes de completar el job.

### Compatibilidad observada en Valery

- `PRODUCTOS_FACTURABLES` relaciona el código facturable; el maestro completo se toma de `PRODUCTOS_TERMINADOS`.
- La base legacy puede conservar en cero campos fiscales derivados de `VENTAS_DETALLES` aunque acepte el `UPDATE`. Por decisión temporal, 0.7.10 no revierte sólo por esos campos; mantiene validación estricta de cantidades, netos, totales y cabecera. Debe revisarse antes de producción.
- Los registros de prueba anteriores a 0.7.9 (`9855`, `9856`) no son referencia válida: carecían de `VENTAS_ESTADOS` y `VENTAS_EXT`, por lo que no aparecían en el Administrador de Documentos.

### Corrección del empaquetado 0.7.10

El Setup 0.7.9 no abría el panel porque excluía `tkinter`/Tcl/Tk. El build ahora incorpora `_tkinter.pyd`, `tcl86t.dll`, `tk86t.dll`, datos Tcl/Tk y el módulo Python; además ejecuta `BAPPS-Sync-Agent.exe --portable-self-test` e inicializa Tcl dentro del binario congelado antes de publicar el instalador.

### Validado y pendiente

- Suite Python del agente: **106 pruebas correctas** el 2026-07-31.
- El binario portable 0.7.10 superó su prueba de importaciones y runtime Tcl/Tk.
- **Pendiente crítico:** instalar 0.7.10 en la PC de Valery, crear un pedido nuevo y comprobar que el PRS aparezca en el Administrador de Documentos. No reutilizar pedidos o correlativos de pruebas anteriores.

```sql
SELECT v.CORRELATIVO, v.DOCUMENTO, v.TEMPORAL,
       COUNT(DISTINCT ve.CORRELATIVO_PRINCIPAL) AS ESTADOS,
       COUNT(DISTINCT vx.CORRELATIVO_PRINCIPAL) AS EXTENSIONES,
       COUNT(DISTINCT vd.NUMERO_LINEA) AS DETALLES
FROM VENTAS v
LEFT JOIN VENTAS_ESTADOS ve ON ve.CORRELATIVO_PRINCIPAL = v.CORRELATIVO
LEFT JOIN VENTAS_EXT vx ON vx.CORRELATIVO_PRINCIPAL = v.CORRELATIVO
LEFT JOIN VENTAS_DETALLES vd ON vd.CORRELATIVO_PRINCIPAL = v.CORRELATIVO
WHERE v.ORDEN_DE_COMPRA = 'COT-...'
GROUP BY v.CORRELATIVO, v.DOCUMENTO, v.TEMPORAL;
```

El resultado esperado es `ESTADOS=1`, `EXTENSIONES=1` y al menos un detalle; después se valida visualmente en Valery antes de considerar apto el escritor.
