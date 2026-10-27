import { useEffect, useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { getClient, getClients } from '@/api/endpoints';
import type { ClientListItem } from '@/api/types';
import { Drawer } from '@/components/Drawer';
import { DrawerPager, paginateDrawerItems } from '@/components/DrawerPager';
import { FilterBar } from '@/components/FilterBar';
import { StatusBadge } from '@/components/StatusBadge';
import { CardsSkeleton, EmptyState, ErrorState, TableSkeleton } from '@/components/states';
import { dateTime, duration, relativeTime, shortIdentifier } from '@/lib/format';
import { useListView } from '@/lib/useListView';
import { RunDrawer } from '@/views/runs/RunDrawer';

const CHIPS = [
    { value: '', label: 'Todos' },
    { value: 'ok', label: 'OK' },
    { value: 'warning', label: 'Warning' },
    { value: 'error', label: 'Alertas' },
    { value: 'enrolled', label: 'Enrolados' },
];

export function Clients() {
    const { search, onSearch, chip, onChip } = useListView();
    const [openClient, setOpenClient] = useState<number | null>(null);
    const [openRun, setOpenRun] = useState<string | null>(null);
    const [runsPage, setRunsPage] = useState(1);
    const [errorsPage, setErrorsPage] = useState(1);

    useEffect(() => {
        setOpenRun(null);
        setRunsPage(1);
        setErrorsPage(1);
    }, [openClient]);

    const query = useQuery({
        queryKey: ['clients', { chip, search }],
        queryFn: () => getClients({ page_size: 100, health: chip || undefined, search: search || undefined }),
        placeholderData: keepPreviousData,
    });

    const detail = useQuery({
        queryKey: ['client', openClient],
        queryFn: () => getClient(openClient!),
        enabled: openClient !== null,
    });

    const c = detail.data;
    const recentRuns = c ? paginateDrawerItems(c.runs, runsPage) : null;
    const errors = c ? paginateDrawerItems(c.errors, errorsPage) : null;

    return (
        <>
            <FilterBar
                searchValue={search}
                onSearch={onSearch}
                searchPlaceholder="nombre o sistema…"
                chips={CHIPS}
                activeChip={chip}
                onChip={onChip}
                count={query.data ? `${query.data.total} clientes` : undefined}
            />

            {query.isPending && <CardsSkeleton cards={8} />}
            {query.isError && (
                <div className="card">
                    <ErrorState error={query.error} onRetry={() => void query.refetch()} />
                </div>
            )}
            {query.data && query.data.data.length === 0 && (
                <div className="card">
                    <EmptyState title="Sin clientes que coincidan" hint="Ajusta los filtros o el término de búsqueda." />
                </div>
            )}

            {query.data && query.data.data.length > 0 && (
                <div className="card-grid">
                    {query.data.data.map((cl: ClientListItem) => (
                        <div className="entity-card" key={cl.id} onClick={() => setOpenClient(cl.id)}>
                            <div className="entity-card__top">
                                <div>
                                    <div className="entity-card__name">{cl.name}</div>
                                    <div className="entity-card__sub">Sistema: {cl.system}</div>
                                </div>
                                <span className="entity-card__badge">
                                    <StatusBadge status={cl.health} tooltip={cl.health_reason ?? undefined} />
                                </span>
                            </div>
                            <div className="entity-card__kpis">
                                <div>
                                    <div className="entity-kpi__value">{cl.agents}</div>
                                    <div className="entity-kpi__label">agentes</div>
                                </div>
                                <div>
                                    <div className="entity-kpi__value">{cl.syncs}</div>
                                    <div className="entity-kpi__label">syncs</div>
                                </div>
                            </div>
                            <div className="entity-card__footer">
                                Última sync: {relativeTime(cl.last_sync)}
                                {cl.open_errors > 0 && (
                                    <span className="err-count">
                                        {cl.open_errors} {cl.open_errors === 1 ? 'alerta' : 'alertas'}
                                    </span>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <Drawer
                open={openClient !== null && openRun === null}
                onClose={() => setOpenClient(null)}
                code={c?.name ?? '…'}
                name={c ? `Sistema ${c.system} · última sync ${dateTime(c.last_sync)}` : undefined}
                status={c?.health ?? null}
                statusTooltip={c?.health_reason ?? undefined}
            >
                {detail.isPending && <TableSkeleton rows={5} cols={3} />}
                {detail.isError && <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />}
                {c && (
                    <>
                        <div className="drawer-metrics">
                            <div className="drawer-metric">
                                <div className="drawer-metric__value">{c.agents}</div>
                                <div className="drawer-metric__label">agentes</div>
                            </div>
                            <div className="drawer-metric">
                                <div className="drawer-metric__value">{c.syncs}</div>
                                <div className="drawer-metric__label">syncs asignados</div>
                            </div>
                            <div className="drawer-metric">
                                <div className="drawer-metric__value" style={{ color: c.open_errors > 0 ? 'var(--st-red-fg)' : undefined }}>
                                    {c.open_errors}
                                </div>
                                <div className="drawer-metric__label">alertas por revisar</div>
                            </div>
                        </div>

                        {c.errors.length > 0 && (
                            <div className="card card--nested">
                                <div className="card__header">
                                    <div className="card__title">Alertas por revisar</div>
                                    <div className="card__header-right kicker" style={{ color: 'var(--st-red-fg)' }}>{c.open_errors}</div>
                                </div>
                                <div className="card__body--flush drawer-list">
                                    {errors?.items.map((r) => (
                                        <div
                                            className="drawer-list__item"
                                            key={r.id}
                                            style={{ cursor: 'pointer' }}
                                            onClick={() => setOpenRun(r.id)}
                                        >
                                            <span className="mono" title={r.id} style={{ fontWeight: 600, color: 'var(--deep-blue)' }}>{shortIdentifier(r.id)}</span>
                                            <span className="mono grow">{r.sync}</span>
                                            <span className="mono" style={{ fontSize: 10.5, color: 'var(--st-red-fg)' }}>{r.error ?? 'SYNC_FAILED'}</span>
                                            <span className="drawer-list__time mono">{dateTime(r.started_at)}</span>
                                            <StatusBadge status={r.status} />
                                        </div>
                                    ))}
                                </div>
                                {errors && (
                                    <DrawerPager
                                        page={errors.currentPage}
                                        pages={errors.pages}
                                        total={c.errors.length}
                                        onPage={setErrorsPage}
                                    />
                                )}
                            </div>
                        )}

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Agentes del cliente</div>
                            </div>
                            <div className="card__body--flush drawer-list">
                                {c.agents_list.map((a) => (
                                    <div className="drawer-list__item" key={a.code}>
                                        <span className="mono" style={{ fontWeight: 600, color: 'var(--deep-blue)' }}>{a.code}</span>
                                        <span className="mono grow cell-dim">{a.machine}</span>
                                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{relativeTime(a.last_heartbeat)}</span>
                                        <StatusBadge status={a.status} />
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Ejecuciones recientes</div>
                            </div>
                            <div className="card__body--flush drawer-list">
                                {c.runs.length === 0 && (
                                    <div className="drawer-list__item" style={{ color: 'var(--text-3)' }}>Sin ejecuciones.</div>
                                )}
                                {recentRuns?.items.map((r) => (
                                    <div
                                        className="drawer-list__item"
                                        key={r.id}
                                        style={{ cursor: 'pointer' }}
                                        onClick={() => setOpenRun(r.id)}
                                    >
                                        <span className="mono" title={r.id} style={{ fontWeight: 600, color: 'var(--deep-blue)' }}>{shortIdentifier(r.id)}</span>
                                        <span className="mono grow">{r.sync}</span>
                                        <span className="drawer-list__time mono">{dateTime(r.started_at)}</span>
                                        <span style={{ fontSize: 11, color: 'var(--text-3)' }}>{duration(r.started_at, r.ended_at)}</span>
                                        <StatusBadge status={r.status} />
                                    </div>
                                ))}
                            </div>
                            {recentRuns && (
                                <DrawerPager
                                    page={recentRuns.currentPage}
                                    pages={recentRuns.pages}
                                    total={c.runs.length}
                                    onPage={setRunsPage}
                                />
                            )}
                        </div>
                    </>
                )}
            </Drawer>

            <RunDrawer runId={openRun} onClose={() => setOpenRun(null)} />
        </>
    );
}
