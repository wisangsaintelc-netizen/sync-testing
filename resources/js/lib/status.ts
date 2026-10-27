/**
 * ÚNICA fuente de color/label por estado (Documentación de diseño §4).
 * El backend envía la clave cruda; aquí se resuelve label + colores.
 * Un valor desconocido cae al gris "Deshabilitado" — no rompe la UI,
 * pero es un bug del backend a corregir.
 *
 * Regla: prohibido definir colores de estado dentro de una vista.
 */

export interface StatusMeta {
    label: string;
    dot: string;
    bg: string;
    fg: string;
}

type Tone = 'green' | 'red' | 'blue' | 'amber' | 'gray';

const TONES: Record<Tone, Omit<StatusMeta, 'label'>> = {
    green: { dot: 'var(--st-green-dot)', bg: 'var(--st-green-bg)', fg: 'var(--st-green-fg)' },
    red: { dot: 'var(--st-red-dot)', bg: 'var(--st-red-bg)', fg: 'var(--st-red-fg)' },
    blue: { dot: 'var(--st-blue-dot)', bg: 'var(--st-blue-bg)', fg: 'var(--st-blue-fg)' },
    amber: { dot: 'var(--st-amber-dot)', bg: 'var(--st-amber-bg)', fg: 'var(--st-amber-fg)' },
    gray: { dot: 'var(--st-gray-dot)', bg: 'var(--st-gray-bg)', fg: 'var(--st-gray-fg)' },
};

const TABLE: Record<string, { label: string; tone: Tone }> = {
    // Agente
    online: { label: 'Online', tone: 'green' },
    offline: { label: 'Offline', tone: 'red' },
    enrolled: { label: 'Enrolado', tone: 'blue' },
    disabled: { label: 'Deshabilitado', tone: 'gray' },
    // Run
    success: { label: 'Success', tone: 'green' },
    running: { label: 'Running', tone: 'blue' },
    failed: { label: 'Failed', tone: 'red' },
    skipped: { label: 'Skipped', tone: 'amber' },
    stopping: { label: 'Stopping', tone: 'amber' },
    interrupted: { label: 'Interrumpido', tone: 'gray' },
    // Comando
    pending: { label: 'Pending', tone: 'amber' },
    claimed: { label: 'Claimed', tone: 'blue' },
    completed: { label: 'Completado', tone: 'green' },
    expired: { label: 'Expirado', tone: 'gray' },
    // Sync
    enabled: { label: 'Habilitado', tone: 'green' },
    paused: { label: 'Pausado', tone: 'amber' },
    // Salud de cliente
    ok: { label: 'OK', tone: 'green' },
    warning: { label: 'Warning', tone: 'amber' },
    error: { label: 'Error', tone: 'red' },
};

const FALLBACK: StatusMeta = { label: 'Deshabilitado', ...TONES.gray };

export function meta(status: string | null | undefined): StatusMeta {
    if (!status) return FALLBACK;
    const entry = TABLE[status];
    if (!entry) return FALLBACK;
    return { label: entry.label, ...TONES[entry.tone] };
}
