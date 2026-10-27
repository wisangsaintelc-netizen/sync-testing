import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getAgents } from '@/api/endpoints';
import type { AgentListItem } from '@/api/types';
import { Card } from '@/components/Card';
import { DataTable, Pager } from '@/components/DataTable';
import type { Column } from '@/components/DataTable';
import { FilterBar } from '@/components/FilterBar';
import { StatusBadge } from '@/components/StatusBadge';
import { EmptyState, ErrorState, TableSkeleton } from '@/components/states';
import { relativeTime } from '@/lib/format';
import { useListView } from '@/lib/useListView';
import { AgentDrawer } from './AgentDrawer';

const CHIPS = [
    { value: '', label: 'Todos' },
    { value: 'online', label: 'Online' },
    { value: 'offline', label: 'Offline' },
    { value: 'enrolled', label: 'Enrolados' },
    { value: 'disabled', label: 'Deshabilitados' },
];

const PAGE_SIZE = 25;

const columns: Column<AgentListItem>[] = [
    { key: 'code', header: 'Agente', render: (a) => <span className="cell-id">{a.code}</span> },
    { key: 'client', header: 'Cliente', render: (a) => a.client },
    { key: 'machine', header: 'Máquina', render: (a) => <span className="cell-mono">{a.machine}</span> },
    { key: 'version', header: 'Versión', render: (a) => <span className="cell-mono">{a.version}</span> },
    { key: 'status', header: 'Estado', render: (a) => <StatusBadge status={a.status} /> },
    { key: 'hb', header: 'Heartbeat', render: (a) => <span className="cell-dim">{relativeTime(a.last_heartbeat)}</span> },
    { key: 'ip', header: 'IP', render: (a) => <span className="cell-mono">{a.ip}</span> },
    { key: 'syncs', header: 'Syncs', render: (a) => <span className="cell-num">{a.syncs_count}</span> },
    {
        key: 'err',
        header: 'Último error',
        render: (a) =>
            a.last_error ? (
                <span className="cell-mono" style={{ color: 'var(--st-red-fg)' }}>{a.last_error}</span>
            ) : (
                <span className="cell-dim">—</span>
            ),
    },
];

export function Agents() {
    const { search, onSearch, chip, onChip, page, setPage } = useListView();
    const [openAgent, setOpenAgent] = useState<string | null>(null);

    const query = useQuery({
        queryKey: ['agents', { page, chip, search }],
        queryFn: () => getAgents({ page, page_size: PAGE_SIZE, status: chip || undefined, search: search || undefined }),
        placeholderData: keepPreviousData,
        refetchInterval: 30_000,
    });

    return (
        <>
            <FilterBar
                searchValue={search}
                onSearch={onSearch}
                searchPlaceholder="código, cliente, máquina o IP…"
                chips={CHIPS}
                activeChip={chip}
                onChip={onChip}
                count={query.data ? `${query.data.total} agentes` : undefined}
            />

            <Card flush>
                {query.isPending && <TableSkeleton rows={10} cols={9} />}
                {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
                {query.data && query.data.data.length === 0 && (
                    <EmptyState title="Sin agentes que coincidan" hint="Ajusta los filtros o el término de búsqueda." />
                )}
                {query.data && query.data.data.length > 0 && (
                    <>
                        <DataTable
                            columns={columns}
                            rows={query.data.data}
                            rowKey={(a) => a.code}
                            onRowClick={(a) => setOpenAgent(a.code)}
                        />
                        <Pager page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} alwaysShow />
                    </>
                )}
            </Card>

            <AgentDrawer agentCode={openAgent} onClose={() => setOpenAgent(null)} />
        </>
    );
}
