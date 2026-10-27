# Despliegue del Centro BAPPS Sync

Este procedimiento despliega el **Centro Laravel**: panel web, API, auditoría,
catálogo, asignaciones y firma de configuraciones. No instala, actualiza ni
reinicia el agente Windows de ningún cliente.

Estado de referencia: PHP de desarrollo validado el 2026-07-28 con
`C:\xampp\php-8.4.23\php.exe`, módulos requeridos y la suite Laravel en verde
(39 pruebas, 231 aserciones).

## Límites y responsabilidades

| Componente | Responsable | Datos que toca | No hace |
|---|---|---|---|
| Centro Laravel | Servidor BAPPS | MySQL central `bapps_sync` | Leer Profit/Valery ni escribir el MySQL del cliente |
| Runtime PHP | Servidor BAPPS | `php.ini` del servidor y caché Laravel | Generar ni exponer claves fuera de `.env` |
| Agente Windows | Máquina del cliente | Origen Profit/Valery y MySQL BAPPS indicado | Descargar código o SQL arbitrario del Centro |

En particular, `AGT-VALERY-01` 0.5.4 está operativo. Este despliegue no
autoriza reinstalarlo, reiniciarlo ni hacer pruebas de desconexión contra su
MySQL/Firebird.

## Requisitos antes de desplegar

### Acceso y respaldo

- Tener una ventana de mantenimiento o confirmar que la migración es compatible
  con el tráfico actual.
- Tener acceso de administrador al servidor web y de migración a MySQL central.
- Respaldar la base central con una cuenta que no se incluya en la línea de
  comandos ni se registre en el historial. Ejemplo orientativo:

  ```powershell
  # Las credenciales viven en un defaults-file protegido, no en esta orden.
  mysqldump --defaults-extra-file=C:\secure\mysql-backup.cnf --single-transaction --routines --triggers bapps_sync > C:\secure\backups\bapps_sync-AAAAmmdd-HHmm.sql
  ```

- Conservar una copia del `.env` actual en un almacén de secretos o respaldo
  cifrado. Sin `APP_KEY` no se pueden leer secretos cifrados existentes; sin la
  clave de recetas no se podrán validar configuraciones firmadas después de
  reinstalar un agente.
- Conservar el artefacto/carpeta de la versión anterior del Centro para poder
  volver a él. No usar `migrate:fresh` ni `migrate:rollback` como mecanismo de
  rollback de producción.

### PHP y extensiones

El proyecto requiere PHP 8.3 o superior. Para el runtime del Centro se exigen:

```text
mbstring, sodium, pdo_mysql, pdo_sqlite, curl, fileinfo, openssl
```

`pdo_sqlite` es necesario para PHPUnit en memoria; los demás son necesarios
para Laravel, MySQL y firma Ed25519. El método aprobado para configurarlo es:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\provision-control-runtime.ps1 -PhpPath 'C:\xampp\php-8.4.23\php.exe'
```

El aprovisionador:

1. valida que las DLL estén presentes;
2. crea `php.ini` desde la plantilla segura si faltaba;
3. hace un respaldo fechado de `php.ini` y lo restaura si falla la validación;
4. habilita y comprueba los módulos;
5. conserva una clave de firma existente en `.env` y limpia la caché de
   configuración de Laravel.

Para un servidor nuevo, sin clave aún, se usa una sola vez el mismo comando con
`-GenerateSigningKey`. La clave se crea con Sodium del PHP local y **no se
muestra** en pantalla:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\provision-control-runtime.ps1 -PhpPath 'C:\xampp\php-8.4.23\php.exe' -GenerateSigningKey
```

La guía operativa del script está en
[`CONTROL_RUNTIME_AUTOMATICO.md`](CONTROL_RUNTIME_AUTOMATICO.md).

> Si Apache/IIS usa otro `php.ini` distinto al PHP de consola, hay que ejecutar
> el aprovisionador contra ese binario o alinear ambos. Tras modificar la
> configuración del PHP servido por Apache, reiniciar Apache antes de validar.

### MySQL central y principio de mínimo privilegio

La base del Centro es `bapps_sync`. No es el MySQL BAPPS de ningún cliente.

- La cuenta de aplicación debe tener solo lectura/escritura sobre `bapps_sync`.
- La cuenta que ejecuta migraciones puede tener permisos DDL temporales sobre
  esa misma base; debe ser distinta de la cuenta de aplicación cuando la
  operación lo permita.
- No otorgar `GRANT ALL` global, ni permisos sobre otras bases, ni exponer MySQL
  central a Internet.
- Usar `utf8mb4` y una colación Unicode coherente, como indica `.env.example`.

## Variables de entorno obligatorias

Crear o completar `.env` desde `.env.example`; nunca versionar ese archivo.
Como mínimo revisar:

```dotenv
APP_ENV=production
APP_DEBUG=false
APP_URL=https://centro.ejemplo.com

APP_KEY=base64:...                         # generar una sola vez por entorno
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=bapps_sync
DB_USERNAME=bapps_sync_app
DB_PASSWORD=...                            # secreto

SESSION_DRIVER=database
CACHE_STORE=database
QUEUE_CONNECTION=database

BAPPS_SYNC_AGENT_ONLINE_THRESHOLD_SECONDS=120
BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY=...  # secreto Ed25519 en base64
BAPPS_SYNC_RECIPE_SIGNING_KEY_ID=recipe-v1
```

Reglas de seguridad para estas variables:

- `APP_KEY` no se rota durante una actualización normal.
- `BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY` tampoco se rota de forma rutinaria.
  Una rotación exige publicar una nueva clave pública a los agentes y un plan de
  transición; cambiarla de improviso invalida configuraciones firmadas.
- El key id no es secreto; la clave privada sí. No incluirla en capturas,
  tickets, comandos, logs ni documentación.
- La carpeta de despliegue y `.env` deben permitir lectura solo a la identidad
  del servidor web y a administradores autorizados.

## Servidor web y TLS

- Publicar como raíz web únicamente la carpeta `public/`, nunca la raíz del
  repositorio. Así `.env`, `vendor/`, `storage/` y los documentos no son
  descargables.
- Forzar HTTPS y redirigir HTTP a HTTPS. El certificado debe ser válido para el
  dominio configurado en `APP_URL`.
- Permitir escritura al usuario del servidor web solo sobre `storage/` y
  `bootstrap/cache/`. El código, `vendor/` y `.env` no deben ser escribibles por
  el proceso web.
- Deshabilitar listado de directorios y revisar que el servidor no sirva
  extensiones `.env`, `.log`, `.sqlite`, `.bak` o `.sql`.
- Aplicar los parches de PHP, servidor web y sistema operativo dentro de la
  política de mantenimiento. XAMPP es válido para este entorno controlado; para
  un servidor expuesto se recomienda un PHP/Apache o IIS mantenido como servicio
  de producción.

## Procedimiento de publicación

### 1. Preparar el artefacto fuera de producción

En la estación de integración o en un staging equivalente:

```powershell
composer install --no-dev --prefer-dist --optimize-autoloader --no-interaction
npm ci
npm run build
& 'C:\xampp\php-8.4.23\php.exe' artisan test
```

Debe terminar con todas las pruebas en verde. Copiar al servidor el código y
los activos compilados de `public/build`; no copiar `.env`, `storage/logs`,
tokens, backups ni artefactos de agentes.

Si se construye directamente en el servidor, hacer estos pasos antes de poner
la nueva carpeta como versión activa. No ejecutar `npm run dev` en producción.

### 2. Poner el Centro en mantenimiento (si hay ventana)

Desde la carpeta de la nueva versión, usando el PHP que atenderá el sitio:

```powershell
& 'C:\xampp\php-8.4.23\php.exe' artisan down
```

La API de agentes quedará temporalmente no disponible. Los agentes conservarán
su última configuración válida y reintentarán por su outbox; no deben perder
trabajo por esta ventana.

### 3. Instalar dependencias y aplicar esquema

Con el respaldo hecho y `.env` presente:

```powershell
composer install --no-dev --prefer-dist --optimize-autoloader --no-interaction
& 'C:\xampp\php-8.4.23\php.exe' artisan migrate:status
& 'C:\xampp\php-8.4.23\php.exe' artisan migrate --force
```

La migración pendiente de esta entrega es:

```text
2026_07_28_010000_create_sync_recipes_tables.php
```

Crea `sync_recipes`, `sync_recipe_versions` y la referencia opcional de
`agent_syncs` a una versión de receta. Es necesaria antes de publicar o asignar
recetas declarativas de Profit. No asignar recetas de Profit a un agente hasta
que el binario del agente que las valida haya sido probado y autorizado.

### 4. Optimizar Laravel y reabrir

```powershell
& 'C:\xampp\php-8.4.23\php.exe' artisan optimize:clear
& 'C:\xampp\php-8.4.23\php.exe' artisan config:cache
& 'C:\xampp\php-8.4.23\php.exe' artisan route:cache
& 'C:\xampp\php-8.4.23\php.exe' artisan view:cache
& 'C:\xampp\php-8.4.23\php.exe' artisan up
```

Reiniciar Apache/IIS o el pool PHP-FPM si cambió `php.ini`, el proceso PHP o la
configuración del host. Luego comprobar que no quede mantenimiento activo:

```powershell
& 'C:\xampp\php-8.4.23\php.exe' artisan about
& 'C:\xampp\php-8.4.23\php.exe' artisan migrate:status
```

## Verificación posterior

Realizar esta lista antes de considerar la publicación exitosa:

- La URL HTTPS carga y el login de un operador funciona.
- `APP_DEBUG=false`: una excepción no muestra stack trace ni secretos.
- La API protegida rechaza una petición sin bearer y acepta un operador válido.
- Dashboard, Agentes, Ejecuciones, Auditoría, Clientes, Catálogo y Asignación
  cargan sin errores de consola o HTTP 500.
- `php artisan migrate:status` no muestra migraciones pendientes.
- El Centro mantiene los datos existentes y los agentes aparecen según su
  heartbeat. No se requieren comandos a `AGT-VALERY-01` para probar el panel.
- `storage/logs/laravel.log` no contiene errores de extensión, conexión MySQL,
  firma o permisos después de la validación.
- Si se publicó la capacidad de recetas: publicar primero una receta de prueba
  en el Centro, comprobar su auditoría y su firma, pero no asignarla al agente
  productivo hasta terminar el piloto aislado.

Ejecutar PHPUnit completo en CI o staging; no hace falta cargar pruebas de
desarrollo sobre la base real de producción.

## Rollback seguro

1. Dejar el Centro en mantenimiento si el fallo afecta datos o autenticación.
2. Conservar el `.env` actual y, especialmente, `APP_KEY` y la clave Ed25519.
3. Volver el servidor web al artefacto anterior y limpiar/recachear la
   configuración de esa versión.
4. No ejecutar de forma automática `php artisan migrate:rollback`: la migración
   de recetas puede contener versiones que no se deben borrar.
5. Si el esquema fuera la causa, restaurar el respaldo de MySQL en una ventana
   aprobada o aplicar una migración correctiva hacia delante. Decidirlo según
   las recetas/asignaciones ya creadas.
6. Revalidar login, API, auditoría y heartbeat antes de retirar mantenimiento.

La vuelta de código anterior es compatible mientras la versión anterior ignore
las tablas y columnas nuevas; aun así, la decisión se toma con el estado real
de la base, no por suposición.

## Despliegue de agente: procedimiento independiente

El instalador de agente y su configuración local pertenecen a otra entrega.
Para el piloto Profit habrá que:

1. empaquetar el agente con el motor declarativo, verificador Ed25519, ODBC SQL
   Server y recetas de solo lectura incluidos;
2. instalarlo primero en una máquina piloto, con perfil local DPAPI para Profit
   y destino MySQL BAPPS;
3. enrolarlo para recibir la clave pública de firma; la clave privada nunca sale
   del Centro;
4. verificar snapshot/sombra/swap, outbox y las pruebas de resiliencia;
5. solo entonces publicar una receta desde el Centro y asignarla.

No se descargan scripts ni SQL desde la web. El Centro entrega una receta
firmada y limitada; la lógica de lectura es código incluido en el agente.

## Evidencia mínima por cada despliegue

Guardar en la auditoría de cambio:

- fecha, responsable, versión/artefacto y motivo;
- hash del artefacto y resultado de pruebas de staging;
- respaldo de base generado y ubicación segura;
- salida de `migrate:status` antes y después;
- confirmación de módulos PHP y de que la clave de recetas fue preservada;
- resultado de la lista de verificación posterior y cualquier rollback.

Esto permite reconstruir exactamente qué se desplegó sin registrar secretos.
