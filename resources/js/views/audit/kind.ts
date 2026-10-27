import type { AuditKind } from '@/api/types';

/** Presentación de la categoría de auditoría (abreviatura + tono). */
export const AUDIT_KIND: Record<AuditKind, { abbr: string; label: string; bg: string; fg: string }> = {
    command: { abbr: 'CMD', label: 'Comando', bg: 'var(--st-blue-bg)', fg: 'var(--st-blue-fg)' },
    event: { abbr: 'EVT', label: 'Evento', bg: 'var(--st-green-bg)', fg: 'var(--st-green-fg)' },
    error: { abbr: 'ERR', label: 'Error', bg: 'var(--st-red-bg)', fg: 'var(--st-red-fg)' },
    config: { abbr: 'CFG', label: 'Config', bg: 'var(--st-amber-bg)', fg: 'var(--st-amber-fg)' },
    auth: { abbr: 'AUT', label: 'Acceso', bg: 'var(--st-gray-bg)', fg: 'var(--st-gray-fg)' },
};

export function kindMeta(kind: string) {
    return AUDIT_KIND[kind as AuditKind] ?? AUDIT_KIND.event;
}
