# BAPPS Sync — Centro de operaciones

Centro de control para agentes de sincronización BAPPS (Valery/Profit → BD BAPPS del cliente).

**Estado actual:** frontend funcional completo (React 19 + TypeScript + Vite sobre Laravel 13) operando contra una **API simulada (MSW)**. El backend Laravel real es la siguiente fase; los handlers de mocks (`resources/js/mocks/handlers.ts`) son la especificación ejecutable del contrato que deberá cumplir.

## Documentación

| Documento | Contenido |
|---|---|
| `docs/BAPPS_SYNC_PLAN_MAESTRO_v1.1.md` | Arquitectura global (centro + agente Python), contratos, QA |
| `docs/PLAN_IMPLEMENTACION_FRONTEND_v1.0.md` | Plan de este frontend (fases F0–F6) |
| `docs/frontend-design/` | Diseño visual, guía técnica y maqueta navegable (servir por HTTP, no `file://`) |

## Desarrollo

Requisitos: PHP 8.4 (Herd), Composer, Node 20+.

```bash
composer install
npm install
cp .env.example .env && php artisan key:generate   # solo primera vez

# levantar (dos terminales o `composer run dev`):
php artisan serve   # http://localhost:8000
npm run dev         # Vite HMR
```

Login demo: cualquier email/contraseña (excepto contraseña `wrong`, que simula credenciales inválidas).

### Mocks

- `VITE_USE_MOCKS=true` en `.env` activa MSW. Con `false`, la app pega a `/api/v1` real.
- Utilidades QA (consola del navegador):
  - `localStorage.setItem('bapps_mock_error','1')` → todos los GET devuelven 500.
  - `localStorage.setItem('bapps_mock_empty','1')` → listados vacíos.
- Los comandos enviados desde la UI transicionan solos (`pending → completed`) y las ejecuciones `running` terminan en ~8–14 s, simulando el ciclo real del agente. `RUN-8841` queda `running` permanente para probar `stop_run`.

## Reglas del frontend (no violar)

1. Colores/labels de estado **solo** desde `resources/js/lib/status.ts` (tabla única). Estado desconocido cae a gris "Deshabilitado".
2. Formateo de fechas/números **solo** en `resources/js/lib/format.ts`; el backend siempre envía ISO 8601 UTC.
3. Mensajes de error operativos/acción sugerida **solo** en `resources/js/lib/errors.ts`.
4. Todo listado: envoltura `{ data, page, page_size, total }`; todo error: `{ error: { code, message } }`.
5. Detalle = drawer 560px con cabecera navy (nunca modal ni página); un solo drawer abierto.
6. Vista de listado nueva = `FilterBar` + tabla o grilla de tarjetas.

## Verificación

```bash
npx tsc --noEmit   # typecheck estricto
npm run build      # build de producción
```
