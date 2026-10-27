import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { IconClose } from '@/components/icons';

type ToastKind = 'success' | 'error';

type ToastItem = {
    id: number;
    kind: ToastKind;
    message: string;
};

type ToastContextValue = {
    success: (message: string) => void;
    error: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
    const [toasts, setToasts] = useState<ToastItem[]>([]);
    const nextId = useRef(0);

    const dismiss = useCallback((id: number) => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
    }, []);

    const show = useCallback((kind: ToastKind, message: string) => {
        const id = ++nextId.current;
        setToasts((current) => [...current, { id, kind, message }].slice(-3));
        window.setTimeout(() => dismiss(id), kind === 'success' ? 4000 : 6500);
    }, [dismiss]);

    return <ToastContext.Provider value={{ success: (message) => show('success', message), error: (message) => show('error', message) }}>
        {children}
        <div className="toast-region" aria-live="polite" aria-atomic="true">
            {toasts.map((toast) => (
                <div className={`toast toast--${toast.kind}`} key={toast.id} role={toast.kind === 'error' ? 'alert' : 'status'}>
                    <span className="toast__symbol" aria-hidden="true">{toast.kind === 'success' ? '✓' : '!'}</span>
                    <span className="toast__message">{toast.message}</span>
                    <button className="toast__close" onClick={() => dismiss(toast.id)} aria-label="Cerrar notificación"><IconClose size={14} /></button>
                </div>
            ))}
        </div>
    </ToastContext.Provider>;
}

export function useToast(): ToastContextValue {
    const context = useContext(ToastContext);
    if (!context) throw new Error('useToast debe usarse dentro de ToastProvider.');

    return context;
}
