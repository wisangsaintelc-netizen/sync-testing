import type { ReactNode } from 'react';

export interface Column<T> {
    key: string;
    header: string;
    render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
    columns: Column<T>[];
    rows: T[];
    rowKey: (row: T) => string;
    onRowClick?: (row: T) => void;
}

/** Tabla estándar: encabezado gris uppercase, filas con hover si son clicables. */
export function DataTable<T>({ columns, rows, rowKey, onRowClick }: DataTableProps<T>) {
    return (
        <div className="table-wrap">
            <table className="table">
                <thead>
                    <tr>
                        {columns.map((c) => (
                            <th key={c.key}>{c.header}</th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr
                            key={rowKey(row)}
                            className={onRowClick ? 'row--click' : undefined}
                            onClick={onRowClick ? () => onRowClick(row) : undefined}
                        >
                            {columns.map((c) => (
                                <td key={c.key}>{c.render(row)}</td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

interface PagerProps {
    page: number;
    pageSize: number;
    total: number;
    onPage: (page: number) => void;
    /** Muestra el resumen aunque todos los registros quepan en una sola página. */
    alwaysShow?: boolean;
}

export function Pager({ page, pageSize, total, onPage, alwaysShow = false }: PagerProps) {
    const pages = Math.max(1, Math.ceil(total / pageSize));
    if (pages <= 1 && !alwaysShow) return null;
    const from = (page - 1) * pageSize + 1;
    const to = Math.min(total, page * pageSize);
    return (
        <div className="pager">
            <span>
                {from}–{to} de {total}
            </span>
            {pages > 1 && (
                <div className="pager__buttons">
                    <button className="btn btn--secondary btn--sm" disabled={page <= 1} onClick={() => onPage(page - 1)}>
                        Anterior
                    </button>
                    <button className="btn btn--secondary btn--sm" disabled={page >= pages} onClick={() => onPage(page + 1)}>
                        Siguiente
                    </button>
                </div>
            )}
        </div>
    );
}
