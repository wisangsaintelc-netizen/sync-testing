# Verificación reproducible

## Resultado del corte

Fecha de ejecución: 2026-08-27.

| Verificación | Resultado |
|---|---|
| Laravel/PHPUnit | `PASS`: 48 pruebas, 48 exitosas, 279 aserciones. |
| Laravel Pint | `PASS`. |
| Rutas Laravel | 36 totales; 31 API, 6 agente, 25 control. |
| Vite producción | `PASS`: Vite 8.1.5, 115 módulos, JS principal 429,56 kB (125,64 kB gzip), CSS 36,52 kB. |
| TypeScript estricto | `FAIL`: 7 errores TS2741 por `direction` ausente en mocks. |
| Agente GUI portable | `PASS` por código de salida 0 en `--portable-self-test`. |
| Servicio portable | `PASS`, mensaje explícito de self-test correcto. |
| Suite Python | No ejecutable con la `.venv` presente; hay 106 métodos de prueba en fuente. |
| Instalador SHA-256/tamaño | Coincide con el handoff vigente. |
| Authenticode | `NotSigned`. |

## Comandos

Desde la raíz del repositorio:

```powershell
& 'C:\xampp\php-8.4.23\php.exe' artisan test
& 'C:\xampp\php-8.4.23\php.exe' vendor\bin\pint --test
& 'C:\xampp\php-8.4.23\php.exe' artisan route:list --json
npm.cmd run build
npx.cmd tsc --noEmit
& '.\agent\dist\BAPPS-Sync-Agent\BAPPS-Sync-Agent.exe' --portable-self-test
& '.\agent\dist\BAPPS-Sync-Service\BAPPS-Sync-Service.exe' --portable-self-test
Get-FileHash '.\agent\release\BAPPS-Sync-Setup-0.7.10.exe' -Algorithm SHA256
Get-AuthenticodeSignature '.\agent\release\BAPPS-Sync-Setup-0.7.10.exe'
```

Para Python, primero recrear el entorno; no reutilizar el ejecutable roto:

```powershell
Set-Location .\agent
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[portable]'
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Fallo TypeScript exacto

Los seis registros iniciales de `resources/js/mocks/db.ts` y el objeto creado en `resources/js/mocks/handlers.ts` cumplen la interfaz antigua de `SyncCatalogItem`. La interfaz vigente exige:

```ts
direction: 'read' | 'write'
```

Vite no bloquea por este error porque su build transpila; por eso build exitoso y typecheck fallido no son resultados contradictorios.

## Qué cubren las pruebas Laravel

- Enrolamiento, rotación y autenticación de agente.
- Configuración schema 1.0/1.1 y destino MySQL.
- Heartbeat, payload máximo y estado online/offline.
- Claims, leases, expiración, ownership e idempotencia de comandos.
- Ingestión idempotente y proyección de eventos/runs.
- Login Sanctum, expiración/revocación y contratos de lectura.
- Configuración/asignación/comandos/inspección.
- CRUD de catálogo/fuentes y publicación atómica de receta.
- Retry, review, provisioning y bootstrap demo.
- Firma y transición de claves del Centro.

No prueban una matriz de roles porque no hay RBAC implementado.

## Qué existe en las 106 pruebas Python

La fuente incluye pruebas para runtime/outbox, API, bootstrap, comando/journal, firmas y rotación, configuración/DPAPI, scheduler, inspección, conexión segura, lector declarativo, sincronizador de clientes, runner, bitácora local y escritor PRS. Hay 18 métodos dedicados al escritor.

Durante este corte no se puede afirmar que las 106 estén verdes con el árbol actual. La última evidencia documental las reporta exitosas en el cierre `0.7.10`, y el auto-test de los binarios empaquetados sí pasa.

## Pruebas externas pendientes

1. Instalar `0.7.10` en el equipo objetivo con un bundle de confianza correcto.
2. Confirmar servicio, permisos, config firmada y conectividad HTTPS.
3. Crear un pedido nuevo, observar claim/lease, escritura y complete.
4. Abrir el PRS en Valery Administrator y validar cabecera, detalles, impuestos, moneda, vigencia y edición/impresión esperada.
5. Repetir idempotentemente el job y confirmar que no duplica.
6. Ejecutar desconexión/reinicio durante el proceso.
7. Ejecutar soak y matriz de resiliencia con volumen real.

## Evidencia no obtenida

No se comprobó estado de migraciones productivas, certificados TLS, backups/restores, configuración real de llaves, firma del instalador, PC instalada, Firebird real, MySQL BAPPS real, API privada de pedidos ni Valery Administrator. Esas comprobaciones requieren ambientes fuera del repositorio.
