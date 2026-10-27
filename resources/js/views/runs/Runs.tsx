import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getRuns } from '@/api/endpoints';
import type { RunListItem } from '@/api/types';
import { Card } from '@/components/Card';
import { DataTable, Pager } from '@/components/DataTable';
import type { Column } from '@/components/DataTable';
import { FilterBar } from '@/components/FilterBar';
import { Notice } from '@/components/Notice';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState, ErrorState, TableSkeleton } from '@/components/states';
import { duration, num, timeOfDay } from '@/lib/format';
import { useListView } from '@/lib/useListView';
import { RunDrawer } from './RunDrawer';

const CHIPS = [
    { value: '', label: 'Todas' },
    { value: 'success', label: 'Success' },
    { value: 'failed', label: 'Failed' },
    { value: 'running', label: 'Running' },
];

const PAGE_SIZE = 25;

const columns: Column<RunListItem>[] = [
    { key: 'id', header: 'Run', render: (r) => <span className="cell-id">{r.id}</span> },
    { key: 'client', header: 'Cliente', render: (r) => r.client },
    { key: 'sync', header: 'Sync', render: (r) => <span className="cell-mono">{r.sync}</span> },
    { key: 'status', header: 'Estado', render: (r) => <StatusBadge status={r.status} /> },
    { key: 'trigger', header: 'Trigger', render: (r) => <span className="cell-mono">{r.trigger}</span> },
    { key: 'start', header: 'Inicio', render: (r) => <span className="cell-dim cell-num">{timeOfDay(r.started_at)}</span> },
    { key: 'dur', header: 'Dur.', render: (r) => <span className="cell-num">{duration(r.started_at, r.ended_at)}</span> },
    { key: 'read', header: 'Leídas', render: (r) => <span className="cell-num">{num(r.rows_read)}</span> },
    {
        key: 'iuf',
        header: 'Ins/Upd/Fail',
        render: (r) => (
            <span className="cell-num cell-dim">
                {r.rows_inserted}/{r.rows_updated}/{r.rows_failed}
            </span>
        ),
    },
    {
        key: 'error',
        header: 'Error',
        render: (r) => (r.error ? <span className="cell-mono" style={{ color: 'var(--st-red-fg)' }}>{r.error}</span> : <span className="cell-dim">—</span>),
    },
];

export function Runs() {
    const { search, onSearch, chip, onChip, page, setPage } = useListView();
    const [openRun, setOpenRun] = useState<string | null>(null);

    const query = useQuery({
        queryKey: ['runs', { page, chip, search }],
        queryFn: () => getRuns({ page, page_size: PAGE_SIZE, status: chip || undefined, search: search || undefined }),
        placeholderData: keepPreviousData,
        // Mantener fresco mientras haya ejecuciones activas visibles.
        refetchInterval: (q) =>
            q.state.data?.data.some((r) => ['pending', 'running', 'stopping'].includes(r.status)) ? 10_000 : false,
    });

    return (
        <>
            <FilterBar
                searchValue={search}
                onSearch={onSearch}
                searchPlaceholder="run_id, cliente o sync…"
                chips={CHIPS}
                activeChip={chip}
                onChip={onChip}
                count={query.data ? `${query.data.total} ejecuciones · últimas 24 h` : undefined}
            />

            <div className="stack">
                <Notice>
                    El manejo de errores se hace desde aquí: abre una ejecución fallida para ver el diagnóstico, la acción
                    sugerida y reintentar.
                </Notice>

                <Card flush>
                    {query.isPending && <TableSkeleton rows={8} cols={10} />}
                    {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
                    {query.data && query.data.data.length === 0 && (
                        <EmptyState title="Sin ejecuciones que coincidan" hint="Ajusta los filtros o el término de búsqueda." />
                    )}
                    {query.data && query.data.data.length > 0 && (
                        <>
                            <DataTable
                                columns={columns}
                                rows={query.data.data}
                                rowKey={(r) => r.id}
                                onRowClick={(r) => setOpenRun(r.id)}
                            />
                            <Pager page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
                        </>
                    )}
                </Card>
            </div>

            <RunDrawer runId={openRun} onClose={() => setOpenRun(null)} />
        </>
    );
}
