# Aprovisionamiento automático del runtime del Centro BAPPS

El Centro Laravel necesita módulos PHP para funcionar y para firmar las recetas
que los agentes ejecutan. No se deben habilitar manualmente uno a uno ni copiar
claves en comandos de consola.

El script `tools/provision-control-runtime.ps1` hace siempre lo mismo:

- verifica que se le indicó un `php.exe` real y que su distribución contiene las
  DLL necesarias;
- crea `php.ini` desde `php.ini-production` si no existe, o respalda el existente;
- habilita y comprueba `mbstring`, `sodium`, `pdo_mysql`, `pdo_sqlite`, `curl`,
  `fileinfo` y `openssl`; `pdo_sqlite` permite que la batería de pruebas use su
  base aislada en memoria;
- deja intacta una clave de firma que ya exista en `.env`;
- puede generar una clave Ed25519 de 64 bytes mediante el mismo PHP del servidor;
- limpia la caché de configuración de Laravel.

La clave nunca se muestra en pantalla ni se guarda en `php.ini`. Solo reside en
`.env`, que no se versiona. Si algo falla durante la preparación, el script
restaura el `php.ini` previo; además conserva un respaldo fechado si ya existía.

## Uso normal en esta instalación

Como la clave ya está en el `.env`, ejecutar una sola vez desde la raíz del
proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\provision-control-runtime.ps1 -PhpPath 'C:\xampp\php-8.4.23\php.exe'
```

Eso no cambia ni revela la clave existente. Al terminar debe informar que
`mbstring` y `sodium` fueron verificadas y que la caché de Laravel se limpió.

## Instalación nueva sin clave

En un servidor nuevo se usa el mismo comando con `-GenerateSigningKey`:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\provision-control-runtime.ps1 -PhpPath 'C:\xampp\php-8.4.23\php.exe' -GenerateSigningKey
```

La clave se genera localmente con PHP/Sodium. Después hay que respaldar el `.env`
de forma segura; si se pierde la clave, las recetas firmadas previamente ya no
podrán validarse tras una reinstalación de los agentes.

## Límites intencionales

El script prepara el runtime del Centro. No modifica XAMPP ni un agente remoto
por sí solo, no instala DLL desde Internet y no rota una clave existente. Esas
acciones requieren una decisión explícita para evitar alterar una instalación
operativa o invalidar agentes ya enrolados.
