import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { IconClose } from './icons';
import { StatusBadge } from './StatusBadge';

interface DrawerProps {
    open: boolean;
    onClose: () => void;
    /** Código/ID principal (mono) en la cabecera navy. */
    code: ReactNode;
    /** Nombre/subtítulo bajo el código. */
    name?: ReactNode;
    status?: string | null;
    statusTooltip?: string;
    actions?: ReactNode;
    children: ReactNode;
}

/**
 * Panel lateral estándar: 560px, cabecera navy, scrim, cierre con Escape.
 * Nunca hay dos drawers abiertos a la vez — el padre garantiza un solo `open`.
 */
export function Drawer({ open, onClose, code, name, status, statusTooltip, actions, children }: DrawerProps) {
    const panelRef = useRef<HTMLDivElement>(null);
    const onCloseRef = useRef(onClose);

    useEffect(() => {
        onCloseRef.current = onClose;
    }, [onClose]);

    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onCloseRef.current();
        };
        document.addEventListener('keydown', onKey);
        panelRef.current?.focus();
        return () => document.removeEventListener('keydown', onKey);
    }, [open]);

    if (!open) return null;

    return createPortal(
        <>
            <div className="scrim" onClick={onClose} />
            <div className="drawer" role="dialog" aria-modal="true" ref={panelRef} tabIndex={-1}>
                <div className="drawer__header">
                    <div className="drawer__header-main">
                        <div className="drawer__code">{code}</div>
                        {name && <div className="drawer__name">{name}</div>}
                    </div>
                    {status !== undefined && <StatusBadge status={status} tooltip={statusTooltip} />}
                    <button className="drawer__close" onClick={onClose} aria-label="Cerrar">
                        <IconClose size={16} />
                    </button>
                </div>
                <div className="drawer__body">{children}</div>
                {actions && <div className="drawer__actions">{actions}</div>}
            </div>
        </>,
        document.body,
    );
}
