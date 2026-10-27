# BAPPS Sync — Paquete de desarrollo v1.1

**Fecha:** 15 de julio de 2026  
**Estado:** Plan consolidado para iniciar implementación con equipo y Codex.  
**Revisión:** doble revisión de arquitectura, coherencia y QA completada.

## Cómo usar este paquete

Este paquete separa las decisiones por responsabilidad para que cada tarea de Codex tenga un contexto pequeño y estable. El orden recomendado de lectura es:

1. `01_ARCHITECTURA_Y_DECISIONES.md`
2. `02_AGENTE_PYTHON.md`
3. `03_CENTRO_LARAVEL_Y_API.md`
4. `04_CONTRATOS_Y_MAQUINAS_DE_ESTADO.md`
5. `05_MODELO_DE_DATOS.md`
6. `06_QA_Y_ESTRATEGIA_DE_PRUEBAS.md`
7. `07_ESCALABILIDAD_100_AGENTES.md`
8. `08_ROADMAP_Y_BACKLOG.md`
9. `09_PLAYBOOK_CODEX.md`
10. `10_ADR_REGISTRO_DECISIONES.md`
11. `11_CHECKLIST_ACEPTACION_MVP.md`
12. `12_CONTRATO_API_CONTROL_v1.md` (contrato React↔Laravel congelado el 17 de julio)

Los contratos JSON de referencia del agente están en `contracts/`. El contrato de la API de control se encuentra en `12_CONTRATO_API_CONTROL_v1.md` y sus fuentes ejecutables viven en `resources/js/api/` y `resources/js/mocks/`.

## Regla principal

> Laravel gobierna y audita. El agente ejecuta y se recupera. Los sincronizadores solo sincronizan. La outbox evita pérdida silenciosa. El frontend presenta y opera.

## Primera entrega end-to-end

La primera vertical slice debe ser `clientes_valery`:

```text
Valery / Firebird
    ↓
BAPPS Sync Agent
    ↓
SyncRunner
    ↓
BD BAPPS del cliente
    ├── datos sincronizados
    ├── sync_success
    └── sync_errors
    ↓
Outbox de telemetría
    ↓ HTTPS
Laravel API
    ↓
MySQL central
    ↓
React: agente, comando, ejecución, métricas y error
```

## Fuentes internas consolidadas

- BAPPS Sync Agent — Especificación técnica v1.0.
- BAPPS Sync — Guía técnica de implementación.
- BAPPS Sync — Documentación y maqueta funcional.
- Decisiones adicionales de arquitectura y QA tomadas durante la revisión del 15 de julio de 2026.
