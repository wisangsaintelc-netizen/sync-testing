import type { ReactNode } from 'react';

interface CardProps {
    title?: ReactNode;
    headerRight?: ReactNode;
    flush?: boolean;
    nested?: boolean;
    children: ReactNode;
    className?: string;
}

export function Card({ title, headerRight, flush, nested, children, className }: CardProps) {
    return (
        <div className={`card${nested ? ' card--nested' : ''}${className ? ` ${className}` : ''}`}>
            {(title || headerRight) && (
                <div className="card__header">
                    {title && <div className="card__title">{title}</div>}
                    {headerRight && <div className="card__header-right">{headerRight}</div>}
                </div>
            )}
            <div className={`card__body${flush ? ' card__body--flush' : ''}`}>{children}</div>
        </div>
    );
}
