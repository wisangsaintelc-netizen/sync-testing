# Especificación técnica para el desarrollo del BAPPS Sync Agent y Centro de Control

**Versión:** 1.0  
**Fecha de decisión:** 9 de julio de 2026  
**Estado:** Aprobado como base de desarrollo  
**Objetivo:** servir como documento de contexto, arquitectura, decisiones técnicas y criterios de implementación para el agente o equipo que inicie el desarrollo.

---

## 1. Propósito del documento

Este documento consolida las decisiones tomadas para evolucionar los sincronizadores actuales, que hoy se ejecutan como scripts Python independientes en PCs o servidores de clientes, hacia una plataforma gobernable, segura, observable y tolerante a fallos.

La prioridad de diseño es, en este orden:

1. **Fiabilidad:** una caída de red, reinicio, error temporal o respuesta perdida no debe provocar pérdida silenciosa de información ni duplicados.
2. **Seguridad:** las bases administrativas locales no se exponen a Internet; los agentes no reciben capacidad de ejecutar comandos arbitrarios.
3. **Manejo explícito de errores:** los errores se clasifican, se registran y se reintentan únicamente cuando corresponde.
4. **Trazabilidad:** toda ejecución relevante debe poder reconstruirse mediante identificadores, estados, tiempos, métricas y errores.
5. **KISS:** no introducir tecnologías, servicios ni capas cuya necesidad no esté demostrada.

Este documento debe considerarse la especificación inicial de arquitectura para empezar el desarrollo del MVP.

---

## 2. Contexto actual

Actualmente existen sincronizadores Python instalados en PCs o servidores de clientes. Estos sincronizadores leen datos de sistemas administrativos locales, por ejemplo:

- Valery sobre Firebird 2.5.
- Profit sobre SQL Server.
- Posibles sistemas futuros basados en MySQL, APIs o archivos.

El caso Valery ya está validado técnicamente: un script Python puede conectarse a Firebird, leer la tabla `CLIENTES` y sincronizar los datos hacia una base remota. El problema que se desea resolver ya no es únicamente la conectividad con la fuente, sino la operación distribuida a escala:

- Saber qué agentes están online.
- Saber qué sincronizadores tiene autorizado cada cliente.
- Activar, pausar o ejecutar un sincronizador.
- Cambiar intervalos sin entrar en la máquina del cliente.
- Ver errores, duración, filas procesadas y resultado de cada ejecución.
- Recuperarse de fallos de red y reinicios.
- Actualizar agentes y conectores de manera controlada en fases posteriores.
- Mantener una arquitectura simple.

El modelo actual, basado en scripts independientes y tareas programadas de Windows, funciona como MVP técnico, pero no proporciona control central, una única estrategia de errores ni trazabilidad operacional suficiente.

---

## 3. Decisión de arquitectura principal

La arquitectura seleccionada es híbrida y distribuida:

```text
PC / servidor del cliente
┌──────────────────────────────────────────────┐
│ BAPPS Sync Agent                             │
│                                              │
│ - Servicio Windows                           │
│ - Scheduler local                            │
│ - SyncRunner                                 │
│ - Cliente HTTPS                              │
│ - Outbox local basada en archivos JSON       │
│ - Logs locales                               │
│ - Conectores                                 │
│ - Sincronizadores                            │
│                                              │
│        │                                     │
│        ▼                                     │
│ Valery / Profit / otro administrativo        │
│ Firebird / SQL Server / otro origen          │
└───────────────────┬──────────────────────────┘
                    │
                    │ HTTPS saliente
                    ▼
┌──────────────────────────────────────────────┐
│ Centro de Control Laravel                    │
│                                              │
│ - Dashboard                                  │
│ - API para agentes                           │
│ - Clientes y sedes                           │
│ - Agentes                                    │
│ - Catálogo de sincronizadores                │
│ - Asignaciones por cliente                   │
│ - Configuración                              │
│ - Comandos                                   │
│ - Ejecuciones                                │
│ - Errores                                    │
│ - Auditoría                                  │
│ - Seguridad                                  │
│                                              │
│        │                                     │
│        ▼                                     │
│ MySQL central                                │
└──────────────────────────────────────────────┘
```

### Regla central de responsabilidades

> **El centro decide qué se puede ejecutar, para quién, cuándo y bajo qué configuración. El agente decide cómo ejecutar de manera segura, idempotente, recuperable y observable.**

---

## 4. Decisiones explícitas de almacenamiento

### 4.1 MySQL central: sí

El sistema tendrá una base MySQL central asociada al centro Laravel.

Esta base almacena, entre otros:

- Clientes.
- Sedes.
- Agentes.
- Catálogo de sincronizadores.
- Sincronizadores asignados a cada cliente.
- Configuraciones.
- Comandos.
- Ejecuciones.
- Errores.
- Auditoría.
- Estado de versiones.

### 4.2 MySQL local en la PC del cliente: no

No se instalará una instancia MySQL local para el agente.

Motivos:

- Añadiría otro servicio que instalar, configurar, actualizar, asegurar y supervisar.
- No resuelve ningún requisito que no pueda resolverse con una outbox local basada en archivos.
- Aumentaría la superficie operativa y violaría KISS.

### 4.3 SQLite local: no

Aunque SQLite sería una opción técnicamente válida para persistir estado operativo, se ha decidido no usarla en el MVP.

El agente utilizará almacenamiento local mínimo basado en archivos para:

- Configuración mínima.
- Logs.
- Eventos pendientes de entrega.
- Opcionalmente, archivos de lock.

### 4.4 El agente no se conecta directamente al MySQL central

La comunicación recomendada es:

```text
Agente Python
     │
     │ HTTPS + JSON
     ▼
API Laravel
     │
     ▼
MySQL central
```

No se recomienda:

```text
Agente Python ──────────────► MySQL central por conexión directa
```

La API Laravel permite centralizar:

- Autenticación.
- Autorización.
- Validación.
- Rate limiting.
- Auditoría.
- Idempotencia.
- Versionado del contrato.
- Sanitización de errores.

Además, evita distribuir credenciales MySQL entre clientes y evita exponer el motor de base de datos a Internet.

---

## 5. Stack tecnológico aprobado

### 5.1 Centro de control

| Capa | Tecnología seleccionada |
|---|---|
| Backend | Laravel 13 |
| Lenguaje | PHP 8.4 |
| Arquitectura | Monolito modular |
| Frontend | Blade + Livewire |
| Base de datos | MySQL 8.4 |
| API | REST JSON versionada |
| Cola interna inicial | Laravel Database Queue |
| Servidor web | Nginx |
| Ejecución PHP | PHP-FPM |
| Sistema operativo | Linux LTS |
| Comunicación con agentes | HTTPS saliente desde el agente |
| Logs | JSON estructurado |

### 5.2 Agente Windows

| Capa | Tecnología seleccionada |
|---|---|
| Lenguaje | Python 3.13.x |
| Empaquetado | PyInstaller |
| Ejecución | Servicio Windows |
| Integración Windows | pywin32 u otra solución equivalente estable |
| HTTP | `requests` o cliente HTTP equivalente |
| Serialización | JSON |
| Persistencia offline | Archivos JSON locales |
| Firebird | `firebirdsql` inicialmente |
| SQL Server | `pyodbc` cuando se incorpore Profit |
| MySQL, si algún conector lo requiere | PyMySQL o driver aprobado |
| Logs | `logging` estructurado |
| Protección de secretos locales | Windows DPAPI o mecanismo equivalente aprobado |

### 5.3 Tecnologías expresamente pospuestas

No se incorporan en el MVP:

- Microservicios.
- Kubernetes.
- Kafka.
- RabbitMQ.
- Redis obligatorio.
- Laravel Horizon.
- WebSockets para agentes.
- MQTT.
- Docker en las PCs de clientes.
- MySQL local.
- SQLite local.
- OpenTelemetry Collector obligatorio.
- Elasticsearch obligatorio.
- mTLS en la primera versión.
- Auto-update remoto del agente en el primer MVP.
- Sincronización bidireccional.
- Escritura hacia Valery o Profit sin una fase de seguridad específica.

Estas tecnologías no se consideran malas; simplemente no existe todavía una necesidad demostrada que justifique su complejidad.

---

## 6. Monolito modular en el centro

El centro Laravel será una sola aplicación desplegable, pero organizada por dominios.

Estructura conceptual:

```text
app/
├── Domains/
│   ├── Clients/
│   ├── Agents/
│   ├── Syncs/
│   ├── Commands/
│   ├── Runs/
│   ├── Errors/
│   ├── Audit/
│   └── Security/
│
├── Http/
│   ├── Controllers/
│   └── Middleware/
│
└── Jobs/
```

No son aplicaciones separadas ni microservicios. El objetivo es mantener una sola unidad de despliegue con límites internos claros.

---

## 7. El agente Windows

En cada PC o servidor del cliente se instalará un único producto:

```text
BAPPS Sync Agent
```

No se instalará un servicio por sincronizador.

Ejemplo:

```text
BAPPS Sync Agent
       │
       ├── clientes_valery
       ├── productos_valery
       ├── ventas_valery
       └── cxc_valery
```

El servicio tendrá inicio automático.

### 7.1 Responsabilidades del agente

El agente será responsable de:

- Arrancar automáticamente con Windows.
- Identificarse ante el centro.
- Enviar heartbeats.
- Obtener y cachear configuración válida.
- Consultar comandos pendientes.
- Ejecutar sincronizadores autorizados.
- Evitar ejecuciones simultáneas del mismo sincronizador.
- Generar `run_id` y `correlation_id`.
- Clasificar errores.
- Aplicar reintentos controlados.
- Mantener una outbox local de eventos críticos.
- Reenviar eventos pendientes cuando el centro vuelva a estar disponible.
- Escribir logs locales estructurados.

### 7.2 Lo que no debe hacer el agente

El agente no debe:

- Exponer puertos entrantes.
- Ejecutar comandos shell arbitrarios provenientes del centro.
- Conectarse directamente al MySQL central.
- Usar una credencial compartida por todos los clientes.
- Registrar secretos completos en logs.
- Reintentar indefinidamente.
- Permitir más de una ejecución simultánea del mismo sincronizador.

---

## 8. Catálogo global y asignación de sincronizadores por cliente

Debe existir un catálogo global de sincronizadores disponibles en la plataforma.

Ejemplo:

```text
clientes_valery
productos_valery
ventas_valery
cxc_valery
clientes_profit
productos_profit
ventas_profit
```

El centro decide cuáles están asignados a cada cliente.

Ejemplo:

```text
Cliente: Ferretería El Martillo
Sistema: Valery

✓ clientes_valery
✓ productos_valery
✓ ventas_valery
✕ cxc_valery
✕ clientes_profit
```

### 8.1 Diferencia entre capacidad y autorización

Debe distinguirse entre:

- **El agente contiene el código del sincronizador.**
- **El cliente está autorizado para ejecutar ese sincronizador.**

Ejemplo:

```text
Agente versión 1.5
Capacidades físicas:

✓ clientes_valery
✓ productos_valery
✓ ventas_valery
✓ cxc_valery
```

Pero el cliente tiene autorizado:

```text
✓ clientes_valery
✓ productos_valery
✕ ventas_valery
✕ cxc_valery
```

Resultado: únicamente se ejecutan `clientes_valery` y `productos_valery`.

No será necesario construir un ejecutable diferente para cada cliente.

---

## 9. Fuente de verdad de configuración

La fuente de verdad es el centro Laravel.

El centro almacena, por sincronizador asignado:

- Código.
- Estado habilitado/deshabilitado.
- Intervalo.
- Configuración operativa no secreta.
- Versión de configuración.
- Versión mínima del agente requerida.

Ejemplo de respuesta:

```json
{
  "config_version": 18,
  "syncs": [
    {
      "code": "clientes_valery",
      "enabled": true,
      "interval_seconds": 300
    },
    {
      "code": "productos_valery",
      "enabled": true,
      "interval_seconds": 900
    },
    {
      "code": "ventas_valery",
      "enabled": false,
      "interval_seconds": 600
    }
  ]
}
```

### 9.1 Configuración cacheada

El agente debe conservar la última configuración válida recibida en un archivo local.

Regla:

```text
Centro disponible
        │
        ▼
Actualizar configuración cacheada

Centro no disponible
        │
        ▼
Continuar temporalmente con la última configuración válida
```

Esta decisión evita que una caída temporal del dashboard detenga automáticamente todas las sincronizaciones ya autorizadas.

El archivo de configuración cacheada debe escribirse atómicamente.

---

## 10. Scheduler local y comandos remotos

Se separan dos conceptos.

### 10.1 Ejecución programada

El agente ejecuta localmente según la configuración cacheada.

Ejemplo:

```text
clientes_valery  → cada 5 minutos
productos_valery → cada 15 minutos
```

### 10.2 Comando remoto

El centro puede solicitar una acción explícita:

- `run_now`
- `pause_sync`
- `resume_sync`
- `refresh_config`

En fases posteriores podrían añadirse:

- `collect_diagnostics`
- `update_interval`
- `update_agent`

No debe existir un comando genérico como:

- `execute_shell`
- `run_powershell`
- `execute_sql_arbitrary`

### 10.3 Una única ruta de ejecución

Tanto el scheduler como `run_now` deben usar el mismo `SyncRunner`.

```text
Scheduler ───┐
             ▼
          SyncRunner ───► clientes_valery.run()
             ▲
run_now ─────┘
```

Esto evita tener dos caminos de ejecución con comportamientos distintos.

---

## 11. Flujo de ejecución de un sincronizador

El `SyncRunner` debe aplicar siempre el mismo flujo:

```text
1. Validar que el sincronizador existe en el agente.
2. Validar que está autorizado para el cliente.
3. Validar que está habilitado.
4. Validar que la configuración es válida.
5. Comprobar que no exista otra ejecución activa del mismo sync.
6. Adquirir lock.
7. Crear run_id y correlation_id.
8. Registrar evento run_started.
9. Ejecutar el sincronizador.
10. Clasificar el resultado.
11. Registrar métricas.
12. Generar run_finished o sync_error.
13. Persistir primero el evento crítico en la outbox local.
14. Intentar enviarlo al centro.
15. Eliminarlo localmente únicamente después de ACK confirmado.
16. Liberar lock.
```

El sincronizador específico debe limitarse a:

```text
Leer origen
    ↓
Validar
    ↓
Transformar
    ↓
Enviar/escribir al destino autorizado
    ↓
Devolver resultado estructurado
```

No debe gestionar por sí mismo:

- Heartbeats.
- Autenticación con el centro.
- Polling de comandos.
- Actualización del agente.
- Estado del servicio Windows.
- Lógica duplicada de reintentos de red.

---

## 12. Outbox local basada en archivos

El mecanismo offline actual, que guarda errores en JSON y los procesa posteriormente, se conserva conceptualmente y se generaliza.

La nueva pieza se denomina:

```text
offline_outbox.py
```

Su objetivo es persistir eventos críticos antes de depender de la red.

### 12.1 Estructura recomendada

```text
BappsSyncAgent/
│
├── bapps-agent.exe
│
├── config/
│   ├── agent.json
│   └── config-cache.json
│
├── outbox/
│   ├── pending/
│   ├── sending/
│   └── failed/
│
└── logs/
    └── agent.log
```

### 12.2 Eventos que deben persistirse

Persistir:

- `run_started`
- `run_finished`
- `sync_error`
- `command_result`
- `diagnostic_result`, si se incorpora más adelante

No persistir indefinidamente:

- Heartbeats históricos.

Los heartbeats se consideran señal de estado actual; no es necesario reproducir centenares de heartbeats antiguos después de una caída.

### 12.3 Regla fundamental

Para eventos críticos:

```text
Persist first
    ↓
Send second
    ↓
Delete after acknowledgment
```

En español:

> Guardar primero, enviar después y eliminar únicamente tras confirmación inequívoca del servidor.

Esta regla protege contra el siguiente caso:

```text
El agente envía un evento
        │
        ▼
Laravel lo procesa correctamente
        │
        ▼
La respuesta HTTP se pierde
        │
        ▼
El agente cree que falló
        │
        ▼
Reenvía el mismo evento
```

Por eso el centro también debe implementar idempotencia por `event_id`.

---

## 13. Un evento por archivo

No utilizar un único archivo que acumule una lista creciente de errores.

No recomendado:

```text
pending_connection_error.json
[
  {...},
  {...},
  {...}
]
```

Recomendado:

```text
outbox/pending/
├── 01JZX8P4YR3HNK9F6T28M4WG5Q.json
├── 01JZX8P87A4H2VVMZ0F7N6SP2C.json
└── 01JZX8PCZEQ0MHQ65Y4S0FB1XX.json
```

Ventajas:

- Una corrupción afecta a un solo evento.
- No hay que reescribir un archivo completo en cada inserción.
- Es más fácil mover eventos entre estados.
- Reduce problemas de concurrencia.
- Simplifica las pruebas.

---

## 14. Identificador único e idempotencia

Cada evento debe tener un `event_id` globalmente único.

Puede usarse UUIDv4 o ULID.

Ejemplo:

```json
{
  "event_id": "01JZX8P4YR3HNK9F6T28M4WG5Q",
  "event_type": "run_finished",
  "agent_id": "AGT-000142",
  "run_id": "RUN-20260709-0001",
  "sync_code": "clientes_valery",
  "status": "success",
  "occurred_at": "2026-07-09T14:45:11-04:00"
}
```

El servidor debe guardar una restricción única sobre `event_id` o aplicar un mecanismo equivalente.

Comportamiento:

```text
Primer POST con event_id ABC
→ procesar
→ guardar
→ responder ACK

Segundo POST con el mismo event_id ABC
→ no duplicar
→ responder ACK idempotente
```

Esta regla es obligatoria para tolerar reenvíos.

---

## 15. Escritura atómica de archivos

No escribir directamente el JSON final en `pending/`.

Secuencia recomendada:

```text
1. Crear archivo temporal en el mismo volumen.
2. Escribir contenido completo.
3. Flush.
4. Cerrar.
5. Renombrar atómicamente al nombre definitivo.
```

Ejemplo:

```text
outbox/pending/.tmp/ABC.tmp
        │
        ▼
Escritura completa
        │
        ▼
os.replace(...)
        │
        ▼
outbox/pending/ABC.json
```

El procesador de outbox debe ignorar archivos temporales.

Esto evita procesar JSON parcialmente escrito después de un corte de energía o cierre abrupto.

---

## 16. Máquina de estados de la outbox

Estados mínimos:

```text
pending
sending
failed
```

Flujo:

```text
pending
   │
   ▼
sending
   │
   ├── ACK válido ─────────────► eliminar
   │
   ├── error retryable ────────► pending
   │
   └── error permanente ───────► failed
```

### 16.1 Recuperación después de crash

Al iniciar, si existen archivos en `sending/` de una ejecución anterior, deben volver a `pending/` salvo que exista evidencia explícita de ACK confirmado.

Esto evita que un crash durante el envío deje eventos abandonados.

---

## 17. Contrato mínimo de evento

Todos los eventos críticos deben compartir una envoltura común.

Ejemplo:

```json
{
  "schema_version": 1,
  "event_id": "01JZX8P4YR3HNK9F6T28M4WG5Q",
  "event_type": "run_finished",
  "agent_id": "AGT-000142",
  "client_id": "CLI-000100",
  "sync_code": "clientes_valery",
  "run_id": "RUN-20260709-0001",
  "correlation_id": "CORR-20260709-ABCD1234",
  "occurred_at": "2026-07-09T14:45:11-04:00",
  "agent_version": "1.0.0",
  "payload": {}
}
```

Reglas:

- `schema_version` permite evolucionar el contrato.
- `event_id` garantiza idempotencia.
- `occurred_at` representa cuándo ocurrió realmente el evento en el agente.
- El servidor también debe guardar `received_at`.
- No incluir secretos.

---

## 18. Ejemplo de run_finished

```json
{
  "schema_version": 1,
  "event_id": "01JZX8P4YR3HNK9F6T28M4WG5Q",
  "event_type": "run_finished",
  "agent_id": "AGT-000142",
  "client_id": "CLI-000100",
  "sync_code": "clientes_valery",
  "run_id": "RUN-20260709-0001",
  "correlation_id": "CORR-20260709-ABCD1234",
  "occurred_at": "2026-07-09T14:45:11-04:00",
  "agent_version": "1.0.0",
  "payload": {
    "status": "success",
    "started_at": "2026-07-09T14:45:03-04:00",
    "finished_at": "2026-07-09T14:45:11-04:00",
    "duration_ms": 8432,
    "rows_read": 369,
    "rows_inserted": 3,
    "rows_updated": 366,
    "rows_deleted": 0,
    "rows_failed": 0
  }
}
```

---

## 19. Ejemplo de sync_error

```json
{
  "schema_version": 1,
  "event_id": "01JZX8P87A4H2VVMZ0F7N6SP2C",
  "event_type": "sync_error",
  "agent_id": "AGT-000142",
  "client_id": "CLI-000100",
  "sync_code": "clientes_valery",
  "run_id": "RUN-20260709-0002",
  "correlation_id": "CORR-20260709-EFGH5678",
  "occurred_at": "2026-07-09T15:01:07-04:00",
  "agent_version": "1.0.0",
  "payload": {
    "error_code": "SOURCE_CONNECTION_FAILED",
    "error_category": "connection",
    "retryable": true,
    "technical_message": "Unable to connect to localhost:3050",
    "operator_message": "No se pudo conectar con Valery en el equipo del cliente.",
    "attempt": 3
  }
}
```

---

## 20. No comprobar Internet mediante 8.8.8.8

El código actual utiliza una comprobación contra `8.8.8.8:53` para decidir si existe Internet.

Ese enfoque no responde a la pregunta relevante.

Puede ocurrir:

```text
8.8.8.8:53                  ✓
sync.bappscloud.com          ✕
```

Por tanto, en el nuevo agente se elimina la dependencia de esa prueba para tomar decisiones operativas.

Regla:

> Intentar directamente la operación real contra la API BAPPS y clasificar el resultado.

Ejemplo:

```text
POST evento
    │
    ├── 200/201/204 → éxito
    ├── timeout     → retryable
    ├── DNS error   → retryable
    ├── 401         → no reintentar infinitamente
    ├── 403         → no reintentar infinitamente
    ├── 409 idempotente → tratar según contrato
    ├── 429         → respetar Retry-After
    └── 5xx         → retryable
```

Puede existir un endpoint de health para diagnóstico, pero no debe usarse como sustituto de la operación real cuando ya es necesario realizarla.

---

## 21. Modelo de errores

No usar únicamente excepciones genéricas o mensajes libres.

Cada error operacional debe convertirse en una estructura consistente.

Códigos iniciales recomendados:

```text
SOURCE_CONNECTION_FAILED
TARGET_CONNECTION_FAILED
CENTRAL_API_UNAVAILABLE
AUTHENTICATION_FAILED
AUTHORIZATION_FAILED
SCHEMA_CHANGED
INVALID_CONFIG
INVALID_DATA
COMMAND_EXPIRED
COMMAND_ALREADY_EXECUTED
SYNC_ALREADY_RUNNING
CHECKPOINT_INVALID
REPORT_DELIVERY_FAILED
OUTBOX_WRITE_FAILED
OUTBOX_EVENT_CORRUPT
UNEXPECTED_ERROR
```

Cada error debe incluir:

```text
error_code
error_category
technical_message
operator_message
retryable
```

Ejemplo:

```text
error_code:
SOURCE_CONNECTION_FAILED

error_category:
connection

technical_message:
Unable to connect to localhost:3050

operator_message:
No se pudo conectar con Valery en el equipo del cliente.

retryable:
true
```

### 21.1 Mensaje técnico y mensaje operativo

No son lo mismo.

- El mensaje técnico ayuda a desarrollo y soporte.
- El mensaje operativo debe ser comprensible para una persona no técnica.

Nunca incluir secretos en ninguno.

---

## 22. Política de reintentos

No todos los errores deben reintentarse.

### Retryable

- Timeout.
- DNS temporal.
- Conexión rechazada por servicio temporalmente caído.
- HTTP 5xx.
- HTTP 429 respetando `Retry-After`.

### No retryable automáticamente

- Credenciales inválidas.
- 401 persistente.
- 403.
- Configuración inválida.
- Cambio de esquema incompatible.
- Datos estructuralmente inválidos.

Política inicial recomendada por operación:

```text
Intento 1
    ↓
Esperar 5 segundos

Intento 2
    ↓
Esperar 15 segundos

Intento 3
    ↓
Fallo final de la operación
```

No existirán reintentos infinitos dentro de una misma ejecución.

El scheduler podrá iniciar otra ejecución futura según su programación.

---

## 23. Manejo de errores críticos

Una utilidad compartida no debe llamar a `sys.exit()` de forma indiscriminada si el proceso completo es un servicio de Windows que administra múltiples sincronizadores.

En el diseño actual existe un patrón de este tipo:

```text
registrar error
    ↓
sys.exit(1)
```

Eso puede derribar todo el agente por un fallo de un sincronizador.

Decisión nueva:

- Las utilidades lanzan excepciones tipadas.
- El `SyncRunner` captura y clasifica.
- El fallo se limita al `run` afectado, salvo que sea un problema realmente fatal del proceso.

Ejemplo:

```text
clientes_valery falla
        │
        ▼
RUN-123 → failed
        │
        ▼
El agente sigue vivo
        │
        ▼
Puede procesar heartbeat, comandos y otros syncs
```

Solo errores verdaderamente fatales del runtime o configuración base del agente deberían provocar la detención controlada del servicio.

---

## 24. Locks y concurrencia

No debe ejecutarse dos veces simultáneamente el mismo sincronizador para el mismo agente.

Flujo:

```text
¿clientes_valery ya está running?
        │
        ├── Sí → skipped / busy
        │
        └── No → adquirir lock y ejecutar
```

Para el MVP, puede utilizarse un lock basado en archivo con creación exclusiva y metadatos:

```json
{
  "sync_code": "clientes_valery",
  "run_id": "RUN-20260709-0001",
  "pid": 4216,
  "created_at": "2026-07-09T14:45:03-04:00"
}
```

Al arrancar, el agente debe poder detectar locks huérfanos de una ejecución anterior y resolverlos de forma segura.

No deben crearse locks globales innecesarios si diferentes sincronizadores pueden ejecutarse de forma independiente.

---

## 25. Estados de una ejecución

Estados iniciales:

```text
pending
running
success
warning
failed
interrupted
skipped
cancelled
```

Para el MVP estricto, pueden comenzar con:

```text
pending
running
success
failed
interrupted
skipped
```

### Semántica

- `pending`: creada pero aún no iniciada.
- `running`: ejecución activa.
- `success`: terminó correctamente.
- `failed`: terminó con error.
- `interrupted`: quedó activa y el proceso reinició o murió.
- `skipped`: no se ejecutó por condición explícita, por ejemplo lock activo.
- `warning`: completó con anomalías parciales, si se incorpora.
- `cancelled`: cancelada de forma controlada, si se incorpora.

---

## 26. Reinicio de Windows o crash del agente

Ejemplo:

```text
Lote 1 → OK
Lote 2 → OK
Lote 3 → PC se apaga
```

Al reiniciar:

```text
Windows inicia
    │
    ▼
BAPPS Sync Agent inicia
    │
    ▼
Revisa locks y estado local mínimo
    │
    ▼
Detecta ejecución anterior no finalizada
    │
    ▼
Genera evento interrupted si corresponde
    │
    ▼
Recupera la operación según reglas del sync
```

La capacidad de volver a ejecutar sin duplicar depende de la idempotencia del sincronizador.

Por tanto:

> Toda sincronización productiva debe diseñarse para ser idempotente siempre que la fuente y el destino lo permitan.

---

## 27. Idempotencia de datos

El sincronizador actual ya utiliza un patrón de clave funcional y upsert.

Ejemplo conceptual:

```text
clave técnica:
id autoincremental

clave funcional:
codigo / rowguid / documento / correlativo
```

La ejecución repetida del mismo lote no debe crear duplicados.

Para cada sincronizador productivo se debe documentar:

- Clave funcional.
- Estrategia de upsert.
- Estrategia de deletes, si aplica.
- Checkpoint, si existe.
- Condiciones bajo las cuales una reejecución es segura.

---

## 28. Sincronización de datos hacia el centro

Decisión arquitectónica recomendada:

```text
Valery / Profit
       │
       ▼
BAPPS Sync Agent
       │
       │ HTTPS + JSON
       ▼
Laravel API
       │
       ▼
MySQL central
```

No:

```text
Agente ─────────► MySQL central directamente
```

La API debe aceptar lotes controlados, validar contratos y aplicar autenticación e idempotencia.

Para tablas grandes, el envío debe realizarse por lotes.

Tamaños iniciales sugeridos para pruebas:

- 100 registros durante desarrollo.
- 500 a 5000 según peso y comportamiento medido.

No fijar un tamaño universal sin pruebas.

---

## 29. API mínima inicial

Endpoints propuestos:

```text
POST /api/v1/agent/enroll
POST /api/v1/agent/heartbeat
GET  /api/v1/agent/config
GET  /api/v1/agent/commands
POST /api/v1/agent/commands/{id}/ack
POST /api/v1/agent/events
```

Se puede utilizar un endpoint único de eventos para `run_started`, `run_finished`, `sync_error` y `command_result`.

Para la carga de datos sincronizados:

```text
POST /api/v1/agent/sync/{sync_code}/batches
```

O endpoints por dominio si la validación lo requiere.

La decisión exacta debe mantenerse simple; no crear decenas de endpoints antes de necesitarlos.

---

## 30. Heartbeat

El heartbeat comunica estado actual.

Ejemplo:

```json
{
  "agent_id": "AGT-000142",
  "version": "1.0.0",
  "machine_name": "SERVER-VALERY",
  "status": "online",
  "local_time": "2026-07-09T14:30:00-04:00",
  "capabilities": ["firebird", "mysql"],
  "running_jobs": []
}
```

No es necesario guardar heartbeats offline para reproducirlos después.

El centro puede determinar pérdida de conectividad mediante `last_seen_at`.

---

## 31. Polling

El agente utilizará HTTPS polling.

Ejemplo de ciclo:

```text
Cada 30 segundos:

1. Enviar heartbeat si corresponde.
2. Consultar comandos pendientes.
3. Consultar versión de configuración.
4. Descargar configuración solo si cambió.
5. Intentar vaciar outbox.
6. Evaluar scheduler local.
```

No se utilizarán WebSockets, MQTT ni conexión permanente en el MVP.

---

## 32. Comandos remotos e idempotencia

Cada comando debe incluir:

```text
command_id
command_type
agent_id
payload
created_at
expires_at
idempotency_key
```

Antes de ejecutar:

```text
¿Está expirado?
    │
    ├── Sí → reportar expired
    │
    └── No
         │
         ▼
¿Ya fue ejecutado?
    │
    ├── Sí → no repetir; devolver resultado idempotente
    │
    └── No
         │
         ▼
¿El tipo está permitido?
    │
    ├── No → rechazar
    │
    └── Sí → ejecutar
```

En ausencia de base local, la lista de comandos procesados puede mantenerse mediante eventos confirmados y un pequeño registro local basado en archivos, limitado por retención.

No almacenar indefinidamente millones de IDs; aplicar una política de retención por tiempo o cantidad.

---

## 33. Seguridad de comunicación

Controles mínimos:

- HTTPS obligatorio.
- TLS moderno.
- Certificados válidos.
- Credencial única por agente.
- Rotación de credenciales.
- Posibilidad de desactivar un agente.
- Comandos permitidos mediante whitelist.
- Expiración de comandos.
- Idempotency keys.
- Rate limiting en la API.
- Auditoría de acciones humanas y comandos.

No abrir:

- Firebird 3050 a Internet.
- SQL Server a Internet.
- MySQL central directamente para agentes.

---

## 34. Enrolamiento del agente

Flujo recomendado:

```text
Instalación
    │
    ▼
Token de enrolamiento de un solo uso
    │
    ▼
POST /api/v1/agent/enroll
    │
    ▼
Laravel valida token
    │
    ▼
Crea identidad individual
    │
    ▼
Devuelve credencial única del agente
```

No usar una misma contraseña para todos los agentes.

La credencial local debe protegerse usando Windows DPAPI o mecanismo equivalente aprobado.

---

## 35. Firma de peticiones y replay protection

Para endpoints críticos puede utilizarse HMAC por agente.

Elementos:

```text
agent_id
timestamp
nonce
body_hash
signature
```

Conceptualmente:

```text
HMAC-SHA256(
    method
    + path
    + body_hash
    + timestamp
    + nonce
)
```

El centro valida:

- Agente existe.
- Agente está habilitado.
- Firma válida.
- Timestamp dentro de ventana.
- Nonce no reutilizado.

Para el MVP puede implementarse de forma progresiva, pero la autenticación individual por agente es obligatoria desde el inicio.

---

## 36. Protección de secretos

No guardar en texto plano sin protección:

- Token de agente.
- Contraseñas de base de datos.
- Connection strings completas.

No registrar en logs:

- Passwords.
- Secretos HMAC.
- Tokens completos.
- Cadenas de conexión con contraseña.

Utilizar Windows DPAPI o mecanismo equivalente para secretos locales.

Los archivos de configuración deben separar claramente:

- Configuración no sensible.
- Referencias a secretos protegidos.

---

## 37. Logs y observabilidad

Campos mínimos por log estructurado:

```text
timestamp
level
agent_id
client_id
sync_code
run_id
correlation_id
event
message
duration_ms
rows_read
rows_written
error_code
agent_version
```

Ejemplo:

```json
{
  "timestamp": "2026-07-09T14:45:11-04:00",
  "level": "INFO",
  "agent_id": "AGT-000142",
  "client_id": "CLI-000100",
  "sync_code": "clientes_valery",
  "run_id": "RUN-20260709-0001",
  "correlation_id": "CORR-20260709-ABCD1234",
  "event": "sync_finished",
  "message": "Sincronización completada",
  "duration_ms": 8432,
  "rows_read": 369,
  "rows_written": 369,
  "error_code": null,
  "agent_version": "1.0.0"
}
```

Alertas futuras recomendadas:

- Agente sin heartbeat por X minutos.
- N fallos consecutivos.
- Cambio de esquema.
- Duración anormal.
- Conteo cero anormal.
- Error de autenticación.
- Error de conexión a la base local.

---

## 38. Estructura inicial del código del agente

```text
agent/
│
├── main.py
├── service.py
├── scheduler.py
├── runner.py
├── api_client.py
├── offline_outbox.py
├── error_classifier.py
├── locks.py
├── security.py
├── logging_config.py
├── config_manager.py
│
├── connectors/
│   ├── firebird.py
│   ├── sqlserver.py
│   └── mysql.py
│
└── syncs/
    ├── clientes_valery.py
    ├── productos_valery.py
    └── ventas_valery.py
```

Aplicar KISS: no crear interfaces, factories o capas abstractas adicionales hasta que exista al menos un segundo caso que demuestre la necesidad.

---

## 39. Interfaz conceptual de un sincronizador

Un sincronizador debería exponer una interfaz simple.

Ejemplo:

```python
class SyncResult:
    status: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_deleted: int
    rows_failed: int
    checkpoint_after: str | None


def run(context) -> SyncResult:
    ...
```

El `context` puede contener:

- Configuración validada.
- `run_id`.
- `correlation_id`.
- Logger contextual.
- Cliente HTTP autorizado.
- Información del agente.

El sincronizador no debe conocer secretos que no necesite.

---

## 40. Migración desde `sync_utils.py`

El archivo actual contiene utilidades útiles, pero debe dividirse por responsabilidad.

### Conservar conceptualmente

- `CancelSyncException`, si se mantiene cancelación interactiva o se adapta a cancelación remota.
- Resumen de métricas.
- Upsert por clave funcional.
- Captura de stack trace para logs técnicos.
- Creación controlada de tablas cuando realmente corresponda.

### Cambiar

#### `log_sync_error`

Dejar de escribir directamente desde cualquier módulo a tablas remotas.

Nuevo flujo:

```text
error
  ↓
ErrorClassifier
  ↓
evento sync_error
  ↓
Outbox local
  ↓
API Laravel
  ↓
MySQL central
```

#### `log_sync_success`

Sustituir por `run_finished` estructurado.

#### `handle_critical_sync_error`

No debe hacer `sys.exit(1)` desde una utilidad compartida.

Debe lanzar una excepción tipada para que el `SyncRunner` decida el alcance del fallo.

#### `upsert_with_sync_check`

Conservar el concepto, pero moverlo al conector o sincronizador correspondiente y documentar la clave funcional usada.

---

## 41. Migración desde `net_error_handler.py`

El archivo actual implementa una primera forma de tolerancia offline mediante JSON. La idea se conserva y se generaliza.

### Conservar

- Persistir localmente cuando el remoto no está disponible.
- Reprocesar después.
- No borrar un archivo hasta completar el envío.
- Compatibilidad con ejecución `.py` y ejecutable empaquetado.

### Sustituir

Eliminar funciones específicas duplicadas como:

```text
save_network_error_to_json()
save_connection_error_to_json()
process_pending_network_errors()
process_pending_connection_errors()
```

Por una API interna uniforme:

```text
outbox.save(event)
outbox.flush()
outbox.ack(event_id)
outbox.fail(event_id, reason)
```

### Corregir la inconsistencia de firmas

Actualmente existe una inconsistencia entre la firma esperada por el procesador de errores pendientes y la firma real de la función de logging.

La nueva arquitectura evita ese problema usando un único objeto `event` validado.

### Eliminar comprobación contra 8.8.8.8

No usar un DNS público para decidir si BAPPS está disponible.

Intentar la operación real y clasificar el error.

### Evitar nombres basados solo en segundos

No usar:

```text
error_sync_modulo_YYYYMMDDTHHMMSS.json
```

Dos eventos del mismo módulo en el mismo segundo pueden colisionar.

Usar UUID o ULID.

### Un archivo por evento

No acumular todos los errores de conexión en un único JSON creciente.

### Escritura atómica

Escribir a temporal y renombrar.

---

## 42. Flujo offline completo

Ejemplo: `clientes_valery` termina correctamente, pero el centro no responde.

```text
clientes_valery finaliza
        │
        ▼
Crear run_finished
        │
        ▼
Asignar event_id único
        │
        ▼
Escribir JSON temporal
        │
        ▼
Renombrar atómicamente a pending/
        │
        ▼
Intentar POST a Laravel
        │
    ┌───┴─────────┐
    ▼             ▼
  ACK           Fallo
    │             │
    ▼             ▼
Eliminar       Conservar
archivo        en pending
                  │
                  ▼
           Reintentar después
```

Cuando vuelve la conectividad:

```text
Agente ejecuta flush de outbox
        │
        ▼
Toma evento pending
        │
        ▼
Mueve a sending
        │
        ▼
POST /api/v1/agent/events
        │
        ├── ACK válido → eliminar
        ├── retryable  → volver a pending
        └── permanente → mover a failed
```

---

## 43. Límites de la outbox

Debe existir una política para evitar crecimiento ilimitado.

Mínimo:

- Métrica de número de eventos pendientes.
- Métrica de bytes ocupados.
- Umbral de warning.
- Umbral crítico.
- Retención para eventos en `failed/`.
- No eliminar silenciosamente eventos críticos pendientes.

Ejemplo de política inicial:

```text
warning:
1.000 eventos o 100 MB

critical:
10.000 eventos o 1 GB
```

Estos valores son configurables y deben ajustarse tras pruebas reales.

---

## 44. Integridad y corrupción de archivos

Si un JSON no puede parsearse:

```text
pending/ABC.json
      │
      ▼
JSON inválido
      │
      ▼
Mover a failed/
      │
      ▼
Registrar OUTBOX_EVENT_CORRUPT
```

No bloquear toda la outbox por un único archivo corrupto.

Opcionalmente, cada evento puede incluir checksum del payload si la necesidad se demuestra.

---

## 45. Ejemplo completo de cliente

```text
Cliente:
Ferretería El Martillo

Sistema:
Valery

Agente:
AGT-000142

Máquina:
SERVER-VALERY
```

Sincronizadores autorizados:

```text
clientes_valery  → activo cada 5 minutos
productos_valery → activo cada 15 minutos
ventas_valery    → pausado
```

Flujo:

```text
Windows inicia
      │
      ▼
BAPPS Sync Agent inicia
      │
      ▼
Carga identidad local
      │
      ▼
Carga última configuración válida
      │
      ▼
Revisa outbox
      │
      ▼
Envía heartbeat
      │
      ▼
Consulta comandos
      │
      ▼
Evalúa scheduler
      │
      ▼
Toca ejecutar clientes_valery
      │
      ▼
Adquiere lock
      │
      ▼
Crea run_id y correlation_id
      │
      ▼
Ejecuta lectura Firebird
      │
      ▼
Envía datos por lotes a API Laravel
      │
      ▼
Genera run_finished
      │
      ▼
Persiste en outbox
      │
      ▼
Envía a Laravel
      │
      ▼
Recibe ACK
      │
      ▼
Elimina evento local
      │
      ▼
Libera lock
```

---

## 46. Modelo de datos central mínimo

### `clients`

```text
id
name
status
created_at
updated_at
```

### `agents`

```text
id
client_id
site_id nullable
agent_code
machine_name
os
version
status
last_seen_at
last_ip
enabled
credential_hash / credential reference
created_at
updated_at
```

### `sync_catalog`

```text
id
code unique
name
source_type
minimum_agent_version
enabled_globally
created_at
updated_at
```

### `client_syncs`

```text
id
client_id
agent_id
sync_catalog_id
enabled
interval_seconds
config_version
config_json
created_at
updated_at
```

### `sync_commands`

```text
id
agent_id
command_type
payload_json
status
idempotency_key unique
created_by
created_at
expires_at
claimed_at
completed_at
result_json
```

### `sync_runs`

```text
id
run_id unique
agent_id
client_id
sync_catalog_id
correlation_id
status
triggered_by
started_at
finished_at
duration_ms
rows_read
rows_inserted
rows_updated
rows_deleted
rows_failed
error_code
error_message
agent_version
created_at
updated_at
```

### `sync_events`

```text
id
event_id unique
schema_version
event_type
agent_id
run_id nullable
correlation_id nullable
occurred_at
received_at
payload_json
created_at
```

### `sync_audit_events`

```text
id
actor_type
actor_id
action
client_id nullable
agent_id nullable
sync_code nullable
metadata_json
created_at
```

---

## 47. Auditoría

Debe registrarse:

- Quién activó o pausó un sincronizador.
- Quién ejecutó `run_now`.
- Cuándo se creó el comando.
- Qué agente lo recibió.
- Cuándo se procesó.
- Resultado.
- Versión del agente.
- Error normalizado.

La auditoría de seguridad no debe depender únicamente de logs volátiles.

---

## 48. Despliegue del agente

El cliente no debe instalar manualmente:

- Python.
- pip.
- virtualenv.
- `firebirdsql`.
- `requests`.
- `pyodbc`.

El objetivo es entregar:

```text
BappsSyncAgentSetup.exe
```

El instalador:

1. Copia archivos.
2. Crea directorios de datos, outbox y logs.
3. Registra el servicio Windows.
4. Solicita o recibe token de enrolamiento.
5. Enrola el agente.
6. Guarda la credencial protegida.
7. Arranca el servicio.

---

## 49. Directorios y permisos

No guardar datos mutables dentro de `Program Files` si eso provoca problemas de permisos.

Estructura recomendada:

```text
C:\Program Files\Bapps\SyncAgent\
    bapps-agent.exe

C:\ProgramData\Bapps\SyncAgent\
    config\
    outbox\
    logs\
    locks\
```

Separar binarios de datos mutables simplifica permisos y actualizaciones.

El servicio debe ejecutar con la cuenta de menor privilegio que permita acceder a la base administrativa requerida.

---

## 50. Pruebas obligatorias del agente

### Unitarias

- Clasificación de errores.
- Cálculo de backoff.
- Serialización de eventos.
- Escritura atómica.
- Transición pending → sending → ACK.
- Recuperación de `sending/` después de crash.
- Detección de JSON corrupto.
- Locks.
- Validación de configuración.

### Integración

- Firebird disponible.
- Firebird caído.
- API disponible.
- API caída.
- Timeout.
- HTTP 401.
- HTTP 403.
- HTTP 429.
- HTTP 500.
- Respuesta perdida después de que el servidor procesa el evento.
- Reenvío del mismo `event_id`.
- Reinicio de Windows durante una ejecución.
- Reinicio durante escritura de outbox.
- Dos intentos simultáneos del mismo sync.

### End-to-end

```text
Valery real o entorno controlado
    ↓
Agente empaquetado
    ↓
API Laravel
    ↓
MySQL central
    ↓
Dashboard
```

---

## 51. Pruebas de seguridad mínimas

- Agente con credencial inválida.
- Agente deshabilitado.
- Comando expirado.
- Comando duplicado.
- `event_id` duplicado.
- Payload demasiado grande.
- Intento de `sync_code` no autorizado.
- Intento de acceder al cliente equivocado.
- Secretos ausentes en logs.
- Rate limiting.
- Reutilización de nonce, si se implementa HMAC.
- Manipulación de `agent_id`.

---

## 52. Criterios de aceptación del MVP

El MVP no se considera completo hasta que demuestre:

1. Un agente Windows instalado como servicio.
2. Enrolamiento individual.
3. Heartbeat visible en Laravel.
4. Configuración central de `clientes_valery`.
5. Asignación del sincronizador a un cliente.
6. Scheduler local.
7. Comando `run_now`.
8. Lock anti-concurrencia.
9. `run_id` y `correlation_id`.
10. Ejecución real de `clientes_valery`.
11. Envío de datos a Laravel por HTTPS.
12. Registro de ejecución en MySQL central.
13. Error clasificado y visible.
14. Outbox basada en JSON.
15. Escritura atómica.
16. Un archivo por evento.
17. Reenvío después de caída de red.
18. Idempotencia por `event_id`.
19. El agente sigue vivo después del fallo de un sincronizador.
20. Logs estructurados sin secretos.

---

## 53. MVP de endpoints

Implementar primero:

```text
POST /api/v1/agent/enroll
POST /api/v1/agent/heartbeat
GET  /api/v1/agent/config
GET  /api/v1/agent/commands
POST /api/v1/agent/commands/{id}/ack
POST /api/v1/agent/events
POST /api/v1/agent/sync/{sync_code}/batches
```

No ampliar la API hasta completar pruebas end-to-end de este circuito.

---

## 54. MVP de comandos

Primera versión:

```text
run_now
pause_sync
resume_sync
refresh_config
```

No añadir actualización remota ni diagnóstico avanzado hasta estabilizar el ciclo principal.

---

## 55. MVP de estados

```text
pending
running
success
failed
interrupted
skipped
```

Agregar `warning` y `cancelled` solo cuando exista semántica definida y casos de uso reales.

---

## 56. Orden recomendado de desarrollo

### Fase 1. Extraer `clientes_valery`

- Convertir el script actual en módulo ejecutable mediante `run(context)`.
- Separar conexión Firebird.
- Separar envío al destino.
- Devolver `SyncResult`.

### Fase 2. Crear `SyncRunner`

- Locks.
- IDs.
- Métricas.
- Excepciones tipadas.
- Estados.

### Fase 3. Crear la outbox

- Un archivo por evento.
- UUID/ULID.
- Escritura atómica.
- Pending/sending/failed.
- Flush.
- ACK idempotente.

### Fase 4. Crear API mínima Laravel

- Enrolamiento.
- Heartbeat.
- Configuración.
- Comandos.
- Eventos.
- Lotes de datos.

### Fase 5. Integrar servicio Windows

- Inicio automático.
- Logs.
- Recuperación tras reinicio.

### Fase 6. Dashboard operativo

- Clientes.
- Agentes.
- Sincronizadores asignados.
- Última ejecución.
- Errores.
- `run_now`.
- Pausar/reanudar.

### Fase 7. Pruebas de caos controladas

- Cortar Internet.
- Matar proceso.
- Reiniciar Windows.
- Duplicar eventos.
- Perder respuestas HTTP.
- Provocar 401, 429 y 500.

---

## 57. Reglas KISS obligatorias

1. Una sola aplicación central Laravel.
2. Un solo agente por máquina.
3. Un único `SyncRunner`.
4. Una única outbox genérica.
5. Un único modelo estructurado de error.
6. Un único contrato base de evento.
7. No instalar base local adicional.
8. No abrir puertos entrantes.
9. No ejecutar shell remoto.
10. No añadir infraestructura hasta demostrar el problema.

---

## 58. No objetivos del MVP

Quedan fuera:

- Escritura bidireccional hacia el ERP.
- Resolución de conflictos multidireccional.
- CDC avanzado en todas las fuentes.
- Auto-update remoto.
- Mappings visuales.
- Kubernetes.
- Microservicios.
- Kafka.
- RabbitMQ.
- Redis obligatorio.
- mTLS obligatorio.
- Observabilidad distribuida avanzada.

---

## 59. Decisiones que no deben reabrirse sin nueva evidencia

Para evitar rehacer discusiones sin motivo, estas decisiones se consideran establecidas para el MVP:

- Centro: Laravel monolítico modular.
- Base central: MySQL.
- Agente: Python empaquetado como servicio Windows.
- Sin MySQL local.
- Sin SQLite local.
- Comunicación agente-centro por HTTPS.
- El agente no se conecta directamente al MySQL central.
- Polling en lugar de WebSockets.
- Outbox local basada en archivos JSON.
- Un evento por archivo.
- Escritura atómica.
- UUID/ULID por evento.
- Idempotencia en servidor.
- Comandos remotos mediante whitelist.
- No shell arbitrario.
- Reintentos limitados y clasificados.
- El fallo de un sync no derriba el agente completo.

Estas decisiones pueden revisarse únicamente si aparecen restricciones reales, métricas o requisitos que las invaliden.

---

## 60. Resumen ejecutivo para el agente de desarrollo

Construir un sistema distribuido con dos componentes:

### Centro

```text
Laravel 13
PHP 8.4
Blade + Livewire
MySQL 8.4
API REST JSON
Database Queue inicialmente
```

### Agente

```text
Python 3.13.x
PyInstaller
Servicio Windows
Sin base local adicional
Outbox JSON basada en archivos
HTTPS polling
Logs estructurados
```

### Regla operacional

```text
Centro:
qué ejecutar, para quién, cuándo y con qué configuración.

Agente:
cómo ejecutar de forma fiable, segura, idempotente y recuperable.
```

### Regla offline

```text
Guardar evento crítico localmente
    ↓
Intentar enviarlo
    ↓
Eliminar solo tras ACK
```

### Regla de seguridad

```text
Nunca exponer Firebird/SQL Server/MySQL del cliente a Internet.
Nunca conectar agentes directamente al MySQL central.
Nunca permitir ejecución remota arbitraria de shell.
```

### Primer objetivo funcional

Completar un flujo end-to-end de `clientes_valery`:

```text
Valery / Firebird
       ↓
BAPPS Sync Agent
       ↓
Outbox + SyncRunner
       ↓
HTTPS
       ↓
Laravel API
       ↓
MySQL central
       ↓
Dashboard con ejecución, métricas y errores
```

El desarrollo debe empezar por este circuito y no por funciones accesorias.

---

## 61. Apéndice A: pseudocódigo del ciclo principal del agente

```python
while service_is_running:
    try:
        recover_stale_sending_events()
        flush_outbox()

        if heartbeat_is_due():
            send_heartbeat()

        poll_commands()
        refresh_config_if_needed()
        run_due_syncs()

    except FatalAgentError as exc:
        log_fatal(exc)
        controlled_shutdown()

    except Exception as exc:
        log_unexpected_agent_loop_error(exc)
        sleep_short_interval()

    sleep(poll_interval)
```

El loop principal no debe morir por una excepción no crítica de un sincronizador.

---

## 62. Apéndice B: pseudocódigo del SyncRunner

```python
def execute(sync_code, trigger):
    validate_sync_exists(sync_code)
    validate_sync_authorized(sync_code)
    validate_sync_enabled(sync_code)

    with acquire_sync_lock(sync_code):
        run_id = new_run_id()
        correlation_id = new_correlation_id()

        persist_and_try_send(
            build_run_started_event(run_id, correlation_id, sync_code, trigger)
        )

        try:
            result = sync_registry[sync_code].run(
                context=build_context(run_id, correlation_id)
            )

            event = build_run_finished_event(result)
            persist_and_try_send(event)
            return result

        except Exception as exc:
            normalized = error_classifier.classify(exc)
            event = build_sync_error_event(normalized)
            persist_and_try_send(event)
            raise
```

---

## 63. Apéndice C: pseudocódigo de la outbox

```python
def save(event):
    validate_event(event)
    temp_path = create_temp_path(event["event_id"])
    final_path = pending_path(event["event_id"])

    write_json_and_flush(temp_path, event)
    atomic_replace(temp_path, final_path)


def flush():
    for path in ordered_pending_events():
        sending_path = move_to_sending(path)

        try:
            response = api.send_event(load_json(sending_path))

            if response.is_acknowledged:
                delete(sending_path)
            elif response.is_retryable:
                move_back_to_pending(sending_path)
            else:
                move_to_failed(sending_path)

        except RetryableNetworkError:
            move_back_to_pending(sending_path)
            break

        except Exception:
            move_to_failed(sending_path)
```

---

## 64. Apéndice D: definición de “terminado” para la primera versión

La primera versión puede considerarse lista para piloto cuando:

- Se instala con un solo instalador.
- Arranca automáticamente como servicio Windows.
- Se enrola con credencial individual.
- Aparece online en el dashboard.
- Descarga configuración.
- Ejecuta `clientes_valery` por scheduler.
- Ejecuta `clientes_valery` por `run_now`.
- Evita duplicidad de ejecución.
- Tolera caída de Internet.
- Conserva eventos críticos offline.
- Los reenvía al volver la conectividad.
- No duplica eventos si se reenvían.
- Un error de sincronización no derriba el servicio completo.
- Los errores aparecen clasificados y comprensibles.
- No se filtran secretos en logs.
- No hay MySQL ni SQLite local.
- El agente no se conecta directamente al MySQL central.

---

## 65. Fuentes internas de contexto utilizadas

- Documento de investigación sobre el centro de control para sincronizadores administrativos.
- Script actual `sync_utils.py`.
- Script actual `net_error_handler.py`.
- Decisiones arquitectónicas consolidadas durante la conversación de diseño.

---

## 66. Conclusión

La solución seleccionada conserva la experiencia que ya existe en los sincronizadores actuales y evita una reescritura conceptual innecesaria.

La mejora principal no consiste en añadir infraestructura, sino en estandarizar:

- Un agente único.
- Un `SyncRunner` único.
- Una outbox única.
- Un contrato de eventos único.
- Un catálogo de sincronizadores central.
- Una asignación explícita por cliente.
- Un modelo de errores único.
- Una API HTTPS versionada.
- Idempotencia y ACK explícitos.

El patrón offline ya presente en los scripts actuales se conserva, pero se fortalece con:

- Un archivo por evento.
- IDs globalmente únicos.
- Escritura atómica.
- Estados `pending`, `sending` y `failed`.
- Reenvío seguro.
- Idempotencia del servidor.
- Eliminación únicamente después de ACK.

Esto mantiene el sistema simple, pero considerablemente más fiable y seguro.
