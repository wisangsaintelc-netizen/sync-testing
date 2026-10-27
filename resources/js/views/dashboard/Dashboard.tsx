import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { getDashboardMetrics } from '@/api/endpoints';
import { Card } from '@/components/Card';
import { DataTable } from '@/components/DataTable';
import { StatusBadge } from '@/components/StatusBadge';
import { ErrorState, TableSkeleton } from '@/components/states';
import { intervalLabel, num, relativeTime, timeOfDay, duration } from '@/lib/format';
import { kindMeta } from '@/views/audit/kind';
import { RunDrawer } from '@/views/runs/RunDrawer';
import { AgentDrawer } from '@/views/agents/AgentDrawer';

export function Dashboard() {
    const [openRun, setOpenRun] = useState<string | null>(null);
    const [openAgent, setOpenAgent] = useState<string | null>(null);

    const query = useQuery({
        queryKey: ['dashboard', 'metrics'],
        queryFn: getDashboardMetrics,
        refetchInterval: 15_000,
    });

    if (query.isPending) {
        return (
            <div className="stack">
                <div className="kpi-strip">
                    {Array.from({ length: 5 }).map((_, i) => (
                        <div className="kpi" key={i}>
                            <div className="skeleton" style={{ height: 12, width: '70%' }} />
                            <div className="skeleton" style={{ height: 26, width: '40%', marginTop: 8 }} />
                        </div>
                    ))}
                </div>
                <Card flush>
                    <TableSkeleton rows={5} cols={4} />
                </Card>
            </div>
        );
    }

    if (query.isError) {
        return (
            <Card flush>
                <ErrorState error={query.error} onRetry={() => void query.refetch()} />
            </Card>
        );
    }

    const m = query.data;

    return (
        <>
            <div className="kpi-strip">
                <div className="kpi">
                    <div className="kpi__label">Agentes totales</div>
                    <div className="kpi__value">{m.agents_total}</div>
                    <div className="kpi__hint kpi__hint--ok">+{m.agents_delta_week} esta semana</div>
                </div>
                <div className="kpi">
                    <div className="kpi__label">Online / Offline</div>
                    <div className="kpi__value">
                        {m.agents_online} <small>/ {m.agents_offline} offline</small>
                    </div>
                    <div className="kpi__hint">reportando heartbeat</div>
                </div>
                <div className="kpi">
                    <div className="kpi__label">Syncs activos</div>
                    <div className="kpi__value">{m.syncs_active}</div>
                    <div className="kpi__hint">en ejecución</div>
                </div>
                <div className="kpi">
                    <div className="kpi__label">Alertas por revisar 24h</div>
                    <div className="kpi__value">{m.failed_runs_24h}</div>
                    <div className={`kpi__hint${m.failed_runs_24h > 0 ? ' kpi__hint--danger' : ''}`}>
                        {m.failed_runs_24h > 0 ? 'requieren atención' : 'sin alertas'}
                    </div>
                </div>
                <div className="kpi">
                    <div className="kpi__label">Eventos auditados 24h</div>
                    <div className="kpi__value">{num(m.audit_events_24h)}</div>
                    <div className="kpi__hint">trazados</div>
                </div>
            </div>

            <div className="dash-grid">
                <Card title="Agentes recientes" headerRight={<Link to="/agents">Ver todos →</Link>} flush>
                    <DataTable
                        columns={[
                            { key: 'code', header: 'Agente', render: (a) => <span className="cell-id">{a.code}</span> },
                            { key: 'client', header: 'Cliente', render: (a) => a.client },
                            { key: 'status', header: 'Estado', render: (a) => <StatusBadge status={a.status} /> },
                            {
                                key: 'hb',
                                header: 'Heartbeat',
                                render: (a) => <span className="cell-dim">{relativeTime(a.last_heartbeat)}</span>,
                            },
                        ]}
                        rows={m.recent_agents}
                        rowKey={(a) => a.code}
                        onRowClick={(a) => setOpenAgent(a.code)}
                    />
                </Card>

                <Card title="Auditoría reciente" headerRight={<Link to="/audit">Ver toda →</Link>} flush>
                    <div className="dash-list">
                        {m.recent_audit.map((e) => {
                            const k = kindMeta(e.kind);
                            return (
                                <div className="dash-audit-item" key={e.id}>
                                    <span className="audit-ico" style={{ background: k.bg, color: k.fg }}>
                                        {k.abbr}
                                    </span>
                                    <div className="grow">
                                        <div>{e.action}</div>
                                        <div className="dash-audit-item__meta">
                                            <span className="mono">{e.target}</span> · {e.actor}
                                        </div>
                                    </div>
                                    <span className="dash-audit-item__time">{timeOfDay(e.at)}</span>
                                </div>
                            );
                        })}
                    </div>
                </Card>

                <Card title="Últimas ejecuciones" headerRight={<Link to="/runs">Ver todas →</Link>} flush>
                    <DataTable
                        columns={[
                            { key: 'id', header: 'Run', render: (r) => <span className="cell-id">{r.id}</span> },
                            { key: 'sync', header: 'Sync', render: (r) => <span className="cell-mono">{r.sync}</span> },
                            { key: 'status', header: 'Estado', render: (r) => <StatusBadge status={r.status} /> },
                            {
                                key: 'dur',
                                header: 'Duración',
                                render: (r) => <span className="cell-num">{duration(r.started_at, r.ended_at)}</span>,
                            },
                        ]}
                        rows={m.recent_runs}
                        rowKey={(r) => r.id}
                        onRowClick={(r) => setOpenRun(r.id)}
                    />
                </Card>

                <Card title="Sincronizadores asignados" flush>
                    <div className="dash-list">
                        {m.assigned_syncs.map((s, i) => (
                            <div className="dash-sync-item" key={`${s.code}-${i}`}>
                                <div className="grow">
                                    <div className="mono" style={{ fontWeight: 600, fontSize: 12.5 }}>{s.code}</div>
                                    <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                                        {s.client} · {intervalLabel(s.interval_seconds)}
                                    </div>
                                </div>
                                <StatusBadge status={s.status} />
                            </div>
                        ))}
                    </div>
                </Card>
            </div>

            <RunDrawer runId={openRun} onClose={() => setOpenRun(null)} />
            <AgentDrawer agentCode={openAgent} onClose={() => setOpenAgent(null)} />
        </>
    );
}
