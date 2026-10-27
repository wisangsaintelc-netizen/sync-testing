/**
 * Todo formateo de fecha/número vive aquí, no en las vistas (Guía Técnica §9).
 * El backend siempre manda ISO 8601 UTC; el frontend formatea.
 */

/** "hace 12 s", "hace 41 m", "hace 2 h 14 m", "hace 3 d" */
export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
    if (!iso) return '—';
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return '—';
    let s = Math.max(0, Math.floor((now.getTime() - then) / 1000));
    if (s < 60) return `hace ${s} s`;
    const m = Math.floor(s / 60);
    if (m < 60) return `hace ${m} m`;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    if (h < 24) return remM > 0 ? `hace ${h} h ${remM} m` : `hace ${h} h`;
    const d = Math.floor(h / 24);
    return `hace ${d} d`;
}

/** Duración entre dos ISO → "8.2 s", "1 m 12 s", "—" si no terminó. */
export function duration(startIso: string | null | undefined, endIso: string | null | undefined): string {
    if (!startIso || !endIso) return '—';
    const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
    if (Number.isNaN(ms) || ms < 0) return '—';
    if (ms < 1000) return `${(ms / 1000).toFixed(1)} s`;
    const s = ms / 1000;
    if (s < 60) return `${s < 10 ? s.toFixed(1) : Math.round(s)} s`;
    const m = Math.floor(s / 60);
    const remS = Math.round(s % 60);
    return remS > 0 ? `${m} m ${remS} s` : `${m} m`;
}

/** Hora local "09:42:11". */
export function timeOfDay(iso: string | null | undefined): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleTimeString('es-VE', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

/** Fecha y hora local "12/07/2026 09:42". */
export function dateTime(iso: string | null | undefined): string {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return '—';
    const date = d.toLocaleDateString('es-VE', {
        day: '2-digit', month: '2-digit', year: 'numeric',
    });
    const time = d.toLocaleTimeString('es-VE', {
        hour: '2-digit', minute: '2-digit', hour12: false,
    });

    return `${date} ${time}`;
}

/** Números con separador de miles fino: 1240 → "1.240". */
export function num(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    return n.toLocaleString('es-VE');
}

/** Segundos de intervalo → "cada 15 min", "cada 4 h", "cada 90 s". */
export function intervalLabel(seconds: number): string {
    if (seconds % 3600 === 0) {
        const h = seconds / 3600;
        return `cada ${h} h`;
    }
    if (seconds % 60 === 0) return `cada ${seconds / 60} min`;
    return `cada ${seconds} s`;
}

/** RUN-451a… / CMD-13EA…; el valor íntegro queda disponible en el atributo title. */
export function shortIdentifier(value: string | null | undefined): string {
    if (!value) return '—';
    const match = value.match(/^([A-Za-z]+-)(.{1,4})/);
    if (match) return `${match[1]}${match[2]}…`;
    return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}
