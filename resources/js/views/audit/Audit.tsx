import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getAudit } from '@/api/endpoints';
import type { AuditEvent } from '@/api/types';
import { Card } from '@/components/Card';
import { DataTable, Pager } from '@/components/DataTable';
import type { Column } from '@/components/DataTable';
import { FilterBar } from '@/components/FilterBar';
import { EmptyState, ErrorState, TableSkeleton } from '@/components/states';
import { dateTime } from '@/lib/format';
import { useListView } from '@/lib/useListView';
import { kindMeta } from './kind';

const CHIPS = [
    { value: '', label: 'Todo' },
    { value: 'command', label: 'Comandos' },
    { value: 'event', label: 'Eventos' },
    { value: 'error', label: 'Errores' },
    { value: 'config', label: 'Config' },
    { value: 'auth', label: 'Accesos' },
];

const PAGE_SIZE = 30;

const columns: Column<AuditEvent>[] = [
    {
        key: 'kind',
        header: 'Tipo',
        render: (e) => {
            const k = kindMeta(e.kind);
            return (
                <span className="audit-ico" style={{ background: k.bg, color: k.fg, width: 42, height: 22, borderRadius: 6 }}>
                    {k.abbr}
                </span>
            );
        },
    },
    { key: 'action', header: 'Acción', render: (e) => e.action },
    { key: 'actor', header: 'Actor', render: (e) => <span className="cell-dim">{e.actor}</span> },
    { key: 'target', header: 'Target', render: (e) => <span className="cell-mono">{e.target}</span> },
    { key: 'ctx', header: 'Contexto', render: (e) => <span className="cell-mono cell-dim">{e.ctx}</span> },
    { key: 'result', header: 'Resultado', render: (e) => <span className="cell-mono">{e.result}</span> },
    { key: 'at', header: 'Momento', render: (e) => <span className="cell-dim cell-num">{dateTime(e.at)}</span> },
];

export function Audit() {
    const { search, onSearch, chip, onChip, page, setPage } = useListView();

    const query = useQuery({
        queryKey: ['audit', { page, chip, search }],
        queryFn: () => getAudit({ page, page_size: PAGE_SIZE, kind: chip || undefined, search: search || undefined }),
        placeholderData: keepPreviousData,
    });

    return (
        <>
            <FilterBar
                searchValue={search}
                onSearch={onSearch}
                searchPlaceholder="acción, actor, target…"
                chips={CHIPS}
                activeChip={chip}
                onChip={onChip}
                count={query.data ? `${query.data.total} eventos` : undefined}
            />

            <Card flush>
                {query.isPending && <TableSkeleton rows={12} cols={7} />}
                {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
                {query.data && query.data.data.length === 0 && (
                    <EmptyState title="Sin eventos de auditoría" hint="Ajusta los filtros o el término de búsqueda." />
                )}
                {query.data && query.data.data.length > 0 && (
                    <>
                        <DataTable columns={columns} rows={query.data.data} rowKey={(e) => e.id} />
                        <Pager page={page} pageSize={PAGE_SIZE} total={query.data.total} onPage={setPage} />
                    </>
                )}
            </Card>
        </>
    );
}
