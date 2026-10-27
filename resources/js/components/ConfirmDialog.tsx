import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';

interface ConfirmDialogProps {
    open: boolean;
    title: string;
    children: ReactNode;
    confirmLabel: string;
    busy?: boolean;
    onCancel: () => void;
    onConfirm: () => void;
}

/** Confirmación estándar para acciones irreversibles dentro del Centro. */
export function ConfirmDialog({ open, title, children, confirmLabel, busy = false, onCancel, onConfirm }: ConfirmDialogProps) {
    const cancelRef = useRef<HTMLButtonElement>(null);
    const onCancelRef = useRef(onCancel);

    useEffect(() => {
        onCancelRef.current = onCancel;
    }, [onCancel]);

    useEffect(() => {
        if (!open) return;
        const onKey = (event: KeyboardEvent) => {
            if (event.key === 'Escape' && !busy) onCancelRef.current();
        };
        document.addEventListener('keydown', onKey);
        cancelRef.current?.focus();
        return () => document.removeEventListener('keydown', onKey);
    }, [open, busy]);

    if (!open) return null;

    return createPortal(
        <>
            <div className="scrim" style={{ zIndex: 70 }} onClick={() => { if (!busy) onCancel(); }} />
            <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-dialog-title">
                <div className="confirm-dialog__header"><div id="confirm-dialog-title">{title}</div></div>
                <div className="confirm-dialog__body">{children}</div>
                <div className="confirm-dialog__actions">
                    <button ref={cancelRef} className="btn btn--secondary" disabled={busy} onClick={onCancel}>Cancelar</button>
                    <button className="btn btn--danger" disabled={busy} onClick={onConfirm}>{busy ? 'Eliminando…' : confirmLabel}</button>
                </div>
            </section>
        </>,
        document.body,
    );
}
