/**
 * Mapa código de error → mensajes de dos niveles + acción sugerida.
 * Fuente: Guía Técnica §6 + Plan Maestro §04-7.
 * `retryable` gobierna el botón "Reintentar" — lo confirma el backend,
 * pero este mapa provee el default por código.
 */

export interface ErrorMeta {
    retryable: boolean;
    opMsg: string;
    action: string;
}

const ERRORS: Record<string, ErrorMeta> = {
    SOURCE_CONNECTION_FAILED: {
        retryable: true,
        opMsg: 'No se pudo conectar al sistema administrativo del cliente.',
        action: 'Verificar que el servicio de la base de datos origen esté activo y accesible desde la máquina del agente.',
    },
    TARGET_CONNECTION_FAILED: {
        retryable: true,
        opMsg: 'No se pudo conectar a la base de datos BAPPS del cliente.',
        action: 'Verificar el servicio MySQL local del cliente y las credenciales del agente.',
    },
    CENTRAL_API_UNAVAILABLE: {
        retryable: true,
        opMsg: 'El centro BAPPS no respondió al enviar el lote.',
        action: 'Revisar conectividad de la máquina del agente hacia el centro. El agente reintenta automáticamente.',
    },
    SYNC_ALREADY_RUNNING: {
        retryable: true,
        opMsg: 'Se intentó ejecutar un sync que ya estaba corriendo.',
        action: 'Esperar a que termine la ejecución activa; el scheduler coalescerá la siguiente.',
    },
    SYNC_NOT_FOUND: {
        retryable: false,
        opMsg: 'El sincronizador solicitado no existe en este agente.',
        action: 'Verificar la asignación del sync al agente en Catálogo/Asignación.',
    },
    SYNC_NOT_AUTHORIZED: {
        retryable: false,
        opMsg: 'El sincronizador no está autorizado para este agente.',
        action: 'Asignar el sync al agente desde la vista de Asignación.',
    },
    SYNC_PAUSED: {
        retryable: false,
        opMsg: 'El sincronizador está pausado.',
        action: 'Reanudar el sync antes de ejecutarlo manualmente.',
    },
    RUN_NOT_ACTIVE: {
        retryable: false,
        opMsg: 'La ejecución ya había terminado cuando llegó la orden de detener.',
        action: 'Ninguna: el stop es idempotente y no tuvo efecto.',
    },
    COMMAND_EXPIRED: {
        retryable: false,
        opMsg: 'El comando expiró antes de que el agente lo reclamara.',
        action: 'Verificar que el agente esté online y volver a enviar el comando.',
    },
    AUTHENTICATION_FAILED: {
        retryable: false,
        opMsg: 'Credenciales del agente rechazadas por el centro.',
        action: 'Re-enrolar el agente o revisar su credencial en el centro.',
    },
    INVALID_CONFIG: {
        retryable: false,
        opMsg: 'La configuración del sync tiene un valor inválido.',
        action: 'Corregir la configuración en la asignación del agente y refrescar config.',
    },
    SCHEMA_CHANGED: {
        retryable: false,
        opMsg: 'La estructura de la tabla origen cambió.',
        action: 'Revisar el esquema del sistema origen y actualizar el sincronizador antes de reintentar.',
    },
    OUTBOX_WRITE_FAILED: {
        retryable: true,
        opMsg: 'El agente no pudo persistir el evento en su outbox local.',
        action: 'Revisar espacio en disco y permisos de C:/ProgramData/Bapps/SyncAgent en la máquina del agente.',
    },
    OUTBOX_EVENT_CORRUPT: {
        retryable: false,
        opMsg: 'Un evento de la outbox local está corrupto.',
        action: 'Revisar la carpeta failed/ de la outbox del agente; el resto de eventos siguen fluyendo.',
    },
    AGENT_RESTARTED: {
        retryable: true,
        opMsg: 'La ejecución quedó interrumpida por un reinicio del agente o de Windows.',
        action: 'El agente reconcilió el estado al arrancar. Reintentar si la ejecución era necesaria.',
    },
    AGENT_ALREADY_RUNNING: {
        retryable: false,
        opMsg: 'Se intentó iniciar una segunda instancia del agente en la misma máquina.',
        action: 'Ninguna: el single-instance lock la detuvo. Revisar por qué se intentó un segundo arranque.',
    },
    LOCAL_LOG_WRITE_FAILED: {
        retryable: true,
        opMsg: 'No se pudo escribir el resultado en sync_success/sync_errors del cliente.',
        action: 'Verificar la BD BAPPS del cliente. El resultado quedó preservado en la telemetría central.',
    },
    VALERY_FIREBIRD_STAGE_FAILED: {
        retryable: true,
        opMsg: 'La operación de escritura en Valery falló durante una fase identificada.',
        action: 'Revisar la fase y la causa del detalle técnico. Corregir el origen y reintentar; la operación es idempotente.',
    },
    VALERY_WRITE_VALIDATION_FAILED: {
        retryable: false,
        opMsg: 'Valery no conservó los totales calculados para el presupuesto.',
        action: 'No se confirmó el presupuesto. Comparar los valores esperados y recibidos del detalle técnico antes de reintentar.',
    },
    VALERY_TAX_MISMATCH: {
        retryable: false,
        opMsg: 'El impuesto del producto en la app no coincide con el maestro de Valery.',
        action: 'Corregir la alícuota del producto en la app o actualizar su maestro desde Valery antes de reintentar.',
    },
};

const UNKNOWN: ErrorMeta = {
    retryable: false,
    opMsg: 'Error no catalogado. Revisar el detalle técnico.',
    action: 'Escalar a desarrollo con el código y el correlation ID.',
};

export function errorMeta(code: string | null | undefined): ErrorMeta {
    if (!code) return UNKNOWN;
    return ERRORS[code] ?? UNKNOWN;
}
