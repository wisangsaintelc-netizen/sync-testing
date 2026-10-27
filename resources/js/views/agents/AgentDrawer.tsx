import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getAgent, sendAgentCommand } from '@/api/endpoints';
import { ApiError } from '@/api/client';
import type { CommandType } from '@/api/types';
import { Drawer } from '@/components/Drawer';
import { DrawerPager, paginateDrawerItems } from '@/components/DrawerPager';
import { CodeBlock } from '@/components/CodeBlock';
import { StatusBadge } from '@/components/StatusBadge';
import { useToast } from '@/components/Toast';
import { ErrorState, TableSkeleton } from '@/components/states';
import { IconBolt, IconPause, IconPlay } from '@/components/icons';
import { dateTime, duration, intervalLabel, num, relativeTime, shortIdentifier, timeOfDay } from '@/lib/format';
import { RunDrawer } from '@/views/runs/RunDrawer';

interface AgentDrawerProps {
    agentCode: string | null;
    onClose: () => void;
}

const COMMAND_SUCCESS_MESSAGES: Record<CommandType, string> = {
    refresh_config: 'Actualización de configuración solicitada.',
    run_now: 'Ejecución manual enviada al agente.',
    stop_run: 'Solicitud para detener la ejecución enviada.',
    pause_sync: 'Pausa del sincronizador solicitada.',
    resume_sync: 'Reanudación del sincronizador solicitada.',
    inspect_source_table: 'Inspección de tabla solicitada.',
};

export function AgentDrawer({ agentCode, onClose }: AgentDrawerProps) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const [openRun, setOpenRun] = useState<string | null>(null);
    const [commandsPage, setCommandsPage] = useState(1);
    const [runsPage, setRunsPage] = useState(1);
    const [timelinePage, setTimelinePage] = useState(1);

    useEffect(() => {
        setOpenRun(null);
        setCommandsPage(1);
        setRunsPage(1);
        setTimelinePage(1);
    }, [agentCode]);

    const query = useQuery({
        queryKey: ['agent', agentCode],
        queryFn: () => getAgent(agentCode!),
        enabled: agentCode !== null,
        // Poll corto mientras haya comandos pendientes o runs activas.
        refetchInterval: (q) => {
            const d = q.state.data;
            if (!d) return false;
            const busy =
                d.commands.some((c) => c.status === 'pending' || c.status === 'claimed') ||
                d.runs.some((r) => r.status === 'running' || r.status === 'stopping');
            return busy ? 5000 : false;
        },
    });

    const agent = query.data;

    const command = useMutation({
        mutationFn: (args: { type: CommandType; sync_code?: string; run_id?: string }) =>
            sendAgentCommand(agentCode!, args.type, { sync_code: args.sync_code, run_id: args.run_id }),
        onSuccess: (_, args) => {
            void queryClient.invalidateQueries({ queryKey: ['agent', agentCode] });
            void queryClient.invalidateQueries({ queryKey: ['runs'] });
            void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
            toast.success(COMMAND_SUCCESS_MESSAGES[args.type]);
        },
        onError: (error) => toast.error(error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo enviar el comando al agente.'),
    });

    const pendingOfType = (type: CommandType, syncCode?: string) =>
        agent?.commands.some(
            (c) =>
                c.type === type &&
                (c.status === 'pending' || c.status === 'claimed') &&
                (syncCode === undefined || c.sync_code === syncCode),
        ) ?? false;

    const configJson = agent
        ? JSON.stringify(agent.config, null, 2)
        : '';
    const commands = agent ? paginateDrawerItems(agent.commands, commandsPage) : null;
    const runs = agent ? paginateDrawerItems(agent.runs, runsPage) : null;
    const timeline = agent ? paginateDrawerItems(agent.timeline, timelinePage) : null;

    return (
        <>
            <Drawer
                open={agentCode !== null && openRun === null}
                onClose={onClose}
                code={agentCode ?? ''}
                name={agent ? `${agent.client} · ${agent.machine}` : '…'}
                status={agent?.status ?? null}
                actions={
                    agent && (
                        <>
                            <button
                                className="btn btn--ghost-light btn--sm"
                                disabled={command.isPending || pendingOfType('refresh_config')}
                                onClick={() => command.mutate({ type: 'refresh_config' })}
                                title="Solicita al agente descargar la configuración vigente; no ejecuta una sincronización."
                            >
                                <IconBolt size={12} />
                                {pendingOfType('refresh_config') ? 'Actualización pendiente…' : 'Actualizar configuración'}
                            </button>
                        </>
                    )
                }
            >
                {query.isPending && <TableSkeleton rows={6} cols={3} />}
                {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}

                {agent && (
                    <>
                        <div className="card card--nested">
                            <div className="card__body">
                                <dl className="drawer-kv">
                                    <div>
                                        <dt>Máquina</dt>
                                        <dd className="mono">{agent.machine}</dd>
                                    </div>
                                    <div>
                                        <dt>Versión</dt>
                                        <dd className="mono">{agent.version}</dd>
                                    </div>
                                    <div>
                                        <dt>Última IP</dt>
                                        <dd className="mono">{agent.ip}</dd>
                                    </div>
                                    <div>
                                        <dt>Heartbeat</dt>
                                        <dd>{relativeTime(agent.last_heartbeat)}</dd>
                                    </div>
                                    <div>
                                        <dt>Outbox</dt>
                                        <dd>
                                            {agent.outbox.pending} pendientes · {num(agent.outbox.sent)} enviados
                                        </dd>
                                    </div>
                                    <div>
                                        <dt>Último error</dt>
                                        <dd>
                                            {agent.last_error ? (
                                                <span className="mono" style={{ color: 'var(--st-red-fg)' }}>{agent.last_error}</span>
                                            ) : (
                                                '—'
                                            )}
                                        </dd>
                                    </div>
                                </dl>
                            </div>
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Sincronizadores asignados</div>
                                <div className="card__header-right kicker">{agent.syncs.length}</div>
                            </div>
                            <div className="card__body--flush drawer-list">
                                {agent.syncs.length === 0 && (
                                    <div className="drawer-list__item" style={{ color: 'var(--text-3)' }}>
                                        Sin sincronizadores asignados.
                                    </div>
                                )}
                                {agent.syncs.map((s) => {
                                    const runningNow = agent.runs.some((r) => r.sync === s.code && (r.status === 'running' || r.status === 'stopping'));
                                    return (
                                        <div className="drawer-list__item" key={s.code}>
                                            <div className="grow">
                                                <div className="mono" style={{ fontWeight: 600 }}>{s.code}</div>
                                                <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{intervalLabel(s.interval_seconds)}</div>
                                            </div>
                                            <StatusBadge status={runningNow ? 'running' : s.status} />
                                            <button
                                                className="btn btn--secondary btn--sm"
                                                title="Ejecutar ahora"
                                                disabled={
                                                    command.isPending ||
                                                    s.status !== 'enabled' ||
                                                    runningNow ||
                                                    pendingOfType('run_now', s.code)
                                                }
                                                onClick={() => command.mutate({ type: 'run_now', sync_code: s.code })}
                                            >
                                                <IconPlay size={11} />
                                                {pendingOfType('run_now', s.code) ? 'Enviado…' : 'Ejecutar'}
                                            </button>
                                            {s.status === 'enabled' ? (
                                                <button
                                                    className="btn btn--secondary btn--sm"
                                                    title="Pausar futuras ejecuciones"
                                                    disabled={command.isPending || pendingOfType('pause_sync', s.code)}
                                                    onClick={() => command.mutate({ type: 'pause_sync', sync_code: s.code })}
                                                >
                                                    <IconPause size={11} />
                                                </button>
                                            ) : s.status === 'paused' ? (
                                                <button
                                                    className="btn btn--secondary btn--sm"
                                                    title="Reanudar"
                                                    disabled={command.isPending || pendingOfType('resume_sync', s.code)}
                                                    onClick={() => command.mutate({ type: 'resume_sync', sync_code: s.code })}
                                                >
                                                    <IconPlay size={11} />
                                                </button>
                                            ) : null}
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Configuración activa</div>
                            </div>
                            <div className="card__body">
                                <CodeBlock>{configJson}</CodeBlock>
                            </div>
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Comandos recientes</div>
                            </div>
                            <div className="card__body--flush drawer-list">
                                {agent.commands.length === 0 && (
                                    <div className="drawer-list__item" style={{ color: 'var(--text-3)' }}>Sin comandos.</div>
                                )}
                                {commands?.items.map((c) => (
                                    <div className="drawer-list__item" key={c.id}>
                                        <span className="mono" title={c.id} style={{ fontWeight: 600, color: 'var(--deep-blue)' }}>{shortIdentifier(c.id)}</span>
                                        <span className="mono grow">{c.type}{c.sync_code ? ` · ${c.sync_code}` : ''}</span>
                                        <span className="drawer-list__actor" title={c.by}>{c.by}</span>
                                        <span className="drawer-list__time mono">{timeOfDay(c.created_at)}</span>
                                        {c.type === 'run_now' && c.status === 'completed' ? (
                                            <span className="badge" style={{ background: 'var(--st-green-bg)', color: 'var(--st-green-fg)' }} title="El agente aceptó la orden; el resultado está en Ejecuciones.">
                                                <span className="badge__dot" style={{ background: 'var(--st-green-dot)' }} />
                                                Enviado
                                            </span>
                                        ) : <StatusBadge status={c.status} />}
                                    </div>
                                ))}
                            </div>
                            {commands && (
                                <DrawerPager
                                    page={commands.currentPage}
                                    pages={commands.pages}
                                    total={agent.commands.length}
                                    onPage={setCommandsPage}
                                />
                            )}
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Ejecuciones recientes</div>
                            </div>
                            <div className="card__body--flush drawer-list">
                                {agent.runs.length === 0 && (
                                    <div className="drawer-list__item" style={{ color: 'var(--text-3)' }}>Sin ejecuciones.</div>
                                )}
                                {runs?.items.map((r) => (
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
                            {runs && (
                                <DrawerPager
                                    page={runs.currentPage}
                                    pages={runs.pages}
                                    total={agent.runs.length}
                                    onPage={setRunsPage}
                                />
                            )}
                        </div>

                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Timeline</div>
                            </div>
                            <div className="card__body">
                                <div className="timeline">
                                    {timeline?.items.map((t, i) => (
                                        <div className="timeline-item" key={i}>
                                            <span
                                                className="timeline-item__dot"
                                                style={{
                                                    background:
                                                        t.type === 'sync_error'
                                                            ? 'var(--st-red-dot)'
                                                            : t.type === 'heartbeat'
                                                              ? 'var(--st-green-dot)'
                                                              : 'var(--st-blue-dot)',
                                                }}
                                            />
                                            <div className="grow">
                                                <div className="timeline-item__event">{t.type}</div>
                                                <div className="timeline-item__detail">{t.detail}</div>
                                            </div>
                                            <span className="timeline-item__at">{timeOfDay(t.at)}</span>
                                        </div>
                                    ))}
                                </div>
                                {timeline && (
                                    <DrawerPager
                                        page={timeline.currentPage}
                                        pages={timeline.pages}
                                        total={agent.timeline.length}
                                        onPage={setTimelinePage}
                                    />
                                )}
                            </div>
                        </div>
                    </>
                )}
            </Drawer>

            {/* Al abrir una ejecución se reemplaza el drawer (nunca dos abiertos). */}
            <RunDrawer runId={openRun} onClose={() => setOpenRun(null)} />
        </>
    );
}
