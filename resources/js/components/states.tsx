import { IconAlert, IconRefresh } from './icons';
import { ApiError } from '@/api/client';

/** Skeleton de tabla con la misma geometría que las filas reales. */
export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
    return (
        <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 12 }} aria-busy="true">
            {Array.from({ length: rows }).map((_, r) => (
                <div key={r} style={{ display: 'flex', gap: 14 }}>
                    {Array.from({ length: cols }).map((_, c) => (
                        <div key={c} className="skeleton" style={{ height: 13, flex: c === 1 ? 2 : 1 }} />
                    ))}
                </div>
            ))}
        </div>
    );
}

/** Skeleton de grilla de tarjetas. */
export function CardsSkeleton({ cards = 6 }: { cards?: number }) {
    return (
        <div className="card-grid" aria-busy="true">
            {Array.from({ length: cards }).map((_, i) => (
                <div key={i} className="entity-card entity-card--static">
                    <div className="skeleton" style={{ height: 16, width: '60%' }} />
                    <div className="skeleton" style={{ height: 12, width: '40%' }} />
                    <div className="skeleton" style={{ height: 30 }} />
                </div>
            ))}
        </div>
    );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
    return (
        <div className="empty-state">
            <div className="empty-state__title">{title}</div>
            {hint && <div className="empty-state__hint">{hint}</div>}
        </div>
    );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
    const message = error instanceof ApiError ? `${error.code}: ${error.message}` : 'Error inesperado.';
    return (
        <div className="error-state" role="alert">
            <IconAlert size={22} />
            <div className="error-state__title">No se pudo cargar la información</div>
            <div className="error-state__msg">{message}</div>
            {onRetry && (
                <button className="btn btn--secondary btn--sm" onClick={onRetry} style={{ marginTop: 6 }}>
                    <IconRefresh size={12} /> Reintentar
                </button>
            )}
        </div>
    );
}
