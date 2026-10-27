import { meta } from '@/lib/status';

interface Props {
    status: string | null | undefined;
    /** Pulso en el punto (para estados "vivos" como running/stopping). */
    pulse?: boolean;
    /** Explicación contextual disponible al pasar el cursor o navegar con teclado. */
    tooltip?: string;
}

export function StatusBadge({ status, pulse, tooltip }: Props) {
    const m = meta(status);
    const live = pulse ?? (status === 'running' || status === 'stopping');
    return (
        <span
            className={`badge${live ? ' badge--pulse' : ''}${tooltip ? ' badge--tooltip' : ''}`}
            style={{ background: m.bg, color: m.fg }}
            data-tooltip={tooltip}
            tabIndex={tooltip ? 0 : undefined}
        >
            <span className="badge__dot" style={{ background: m.dot }} />
            {m.label}
        </span>
    );
}
