import type { ReactNode } from 'react';
import { IconInfo } from './icons';

/** Aviso informativo azul — para contexto/ayuda inline, nunca para errores. */
export function Notice({ children }: { children: ReactNode }) {
    return (
        <div className="notice">
            <IconInfo size={15} />
            <div>{children}</div>
        </div>
    );
}
