import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { getRun, retryRun, reviewRun, sendAgentCommand } from '@/api/endpoints';
import { ApiError } from '@/api/client';
import { Drawer } from '@/components/Drawer';
import { CodeBlock } from '@/components/CodeBlock';
import { Notice } from '@/components/Notice';
import { useToast } from '@/components/Toast';
import { ErrorState, TableSkeleton } from '@/components/states';
import { IconPlay, IconStop } from '@/components/icons';
import { errorMeta } from '@/lib/errors';
import { dateTime, duration, num, timeOfDay } from '@/lib/format';

const EVENT_TONES: Record<string, string> = {
    run_started: 'var(--st-blue-dot)',
    batch_sent: 'var(--st-blue-dot)',
    run_finished: 'var(--st-green-dot)',
    sync_error: 'var(--st-red-dot)',
    run_skipped: 'var(--st-amber-dot)',
    stop_requested: 'var(--st-amber-dot)',
    run_interrupted: 'var(--st-gray-dot)',
};

interface RunDrawerProps {
    runId: string | null;
    onClose: () => void;
}

export function RunDrawer({ runId, onClose }: RunDrawerProps) {
    const queryClient = useQueryClient();
    const toast = useToast();

    const query = useQuery({
        queryKey: ['run', runId],
        queryFn: () => getRun(runId!),
        enabled: runId !== null,
        // Ejecución activa: refrescar cada 5 s hasta estado terminal.
        refetchInterval: (q) =>
            q.state.data && ['pending', 'running', 'stopping'].includes(q.state.data.status) ? 5000 : false,
    });

    const run = query.data;

    const retry = useMutation({
        mutationFn: () => retryRun(runId!),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['runs'] });
            void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
            toast.success('Reintento encolado correctamente.');
            onClose();
        },
        onError: (error) => toast.error(error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo reintentar la ejecución.'),
    });

    const stop = useMutation({
        mutationFn: () => sendAgentCommand(run!.agent, 'stop_run', { run_id: run!.id }),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['run', runId] });
            void queryClient.invalidateQueries({ queryKey: ['runs'] });
            toast.success('Solicitud para detener la ejecución enviada.');
        },
        onError: (error) => toast.error(error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo detener la ejecución.'),
    });

    const review = useMutation({
        mutationFn: () => reviewRun(runId!),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['run', runId] });
            void queryClient.invalidateQueries({ queryKey: ['runs'] });
            void queryClient.invalidateQueries({ queryKey: ['clients'] });
            void queryClient.invalidateQueries({ queryKey: ['client'] });
            void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
            toast.success('Ejecución marcada como revisada.');
        },
        onError: (error) => toast.error(error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo marcar la ejecución como revisada.'),
    });

    const em = run?.error ? errorMeta(run.error) : null;
    const isActive = run?.status === 'running' || run?.status === 'stopping';
    const isReviewed = run?.reviewed_at !== null && run?.reviewed_at !== undefined;

    const payload = run
        ? JSON.stringify(
              {
                  run_id: run.id,
                  sync: run.sync,
                  agent: run.agent,
                  trigger: run.trigger,
                  rows_read: run.rows_read,
                  rows_inserted: run.rows_inserted,
                  rows_updated: run.rows_updated,
                  rows_failed: run.rows_failed,
                  correlation_id: run.correlation_id,
              },
              null,
              2,
          )
        : '';

    return (
        <Drawer
            open={runId !== null}
            onClose={onClose}
            code={runId ?? ''}
            name={run ? `${run.client} · ${run.sync}` : '…'}
            status={run?.status ?? null}
            actions={
                run && (
                    <>
                        {isActive && (
                            <button
                                className="btn btn--danger btn--sm"
                                disabled={stop.isPending || run.status === 'stopping'}
                                onClick={() => stop.mutate()}
                            >
                                <IconStop size={12} />
                                {run.status === 'stopping' ? 'Deteniendo…' : 'Detener ejecución'}
                            </button>
                        )}
                        {run.status === 'failed' && em?.retryable && (
                            <button className="btn btn--accent btn--sm" disabled={retry.isPending} onClick={() => retry.mutate()}>
                                <IconPlay size={12} />
                                {retry.isPending ? 'Reintentando…' : 'Reintentar ejecución'}
                            </button>
                        )}
                        {run.status === 'failed' && (
                            <button className="btn btn--ghost-light btn--sm" disabled={review.isPending || isReviewed} onClick={() => review.mutate()}>
                                {isReviewed ? 'Revisado ✓' : review.isPending ? 'Marcando…' : 'Marcar revisado'}
                            </button>
                        )}
                    </>
                )
            }
        >
            {query.isPending && <TableSkeleton rows={5} cols={3} />}
            {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}

            {run && (
                <>
                    <div className="drawer-metrics">
                        <div className="drawer-metric">
                            <div className="drawer-metric__value">{num(run.rows_read)}</div>
                            <div className="drawer-metric__label">filas leídas</div>
                        </div>
                        <div className="drawer-metric">
                            <div className="drawer-metric__value">{num(run.rows_inserted)}</div>
                            <div className="drawer-metric__label">insertadas</div>
                        </div>
                        <div className="drawer-metric">
                            <div className="drawer-metric__value">{num(run.rows_failed)}</div>
                            <div className="drawer-metric__label">fallidas</div>
                        </div>
                    </div>

                    <div className="card card--nested">
                        <div className="card__body">
                            <dl className="drawer-kv">
                                <div>
                                    <dt>Trigger</dt>
                                    <dd className="mono">{run.trigger}</dd>
                                </div>
                                <div>
                                    <dt>Duración</dt>
                                    <dd>{duration(run.started_at, run.ended_at)}</dd>
                                </div>
                                <div>
                                    <dt>Actualizadas</dt>
                                    <dd>{num(run.rows_updated)}</dd>
                                </div>
                                <div>
                                    <dt>Agente</dt>
                                    <dd className="mono" style={{ color: 'var(--deep-blue)', fontWeight: 600 }}>{run.agent}</dd>
                                </div>
                            </dl>
                        </div>
                    </div>

                    <div className="card card--nested">
                        <div className="card__header">
                            <div className="card__title">Timeline de la ejecución</div>
                        </div>
                        <div className="card__body">
                            <div className="timeline">
                                {run.timeline.map((t, i) => (
                                    <div className="timeline-item" key={i}>
                                        <span
                                            className="timeline-item__dot"
                                            style={{ background: EVENT_TONES[t.event] ?? 'var(--st-gray-dot)' }}
                                        />
                                        <div className="grow">
                                            <div className="timeline-item__event">{t.event}</div>
                                            <div className="timeline-item__detail">{t.detail}</div>
                                        </div>
                                        <span className="timeline-item__at">{timeOfDay(t.at)}</span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {run.status === 'failed' && run.error && em && (
                        <div className="card card--nested">
                            <div className="card__header">
                                <div className="card__title">Manejo del error</div>
                            </div>
                            <div className="card__body errbox">
                                <div className="errbox__code">
                                    {run.error}
                                    <span
                                        className="badge"
                                        style={
                                            em.retryable
                                                ? { background: 'var(--st-amber-bg)', color: 'var(--st-amber-fg)' }
                                                : { background: 'var(--st-gray-bg)', color: 'var(--st-gray-fg)' }
                                        }
                                    >
                                        <span
                                            className="badge__dot"
                                            style={{ background: em.retryable ? 'var(--st-amber-dot)' : 'var(--st-gray-dot)' }}
                                        />
                                        {em.retryable ? 'Reintentable' : 'No reintentable'}
                                    </span>
                                </div>
                                <div>
                                    <div className="errbox__level">OPERATIVO</div>
                                    <div className="errbox__op">{em.opMsg}</div>
                                </div>
                                {run.tech_message && (
                                    <div>
                                        <div className="errbox__level">TÉCNICO</div>
                                        <div className="errbox__tech">{run.tech_message}</div>
                                    </div>
                                )}
                                <div>
                                    <div className="errbox__level" style={{ marginBottom: 5 }}>ACCIÓN SUGERIDA</div>
                                    <Notice>{em.action}</Notice>
                                </div>
                                {isReviewed && (
                                    <div>
                                        <div className="errbox__level">REVISIÓN</div>
                                        <div className="errbox__op">Revisado el {dateTime(run.reviewed_at)}.</div>
                                    </div>
                                )}
                            </div>
                        </div>
                    )}

                    <div className="card card--nested">
                        <div className="card__header">
                            <div className="card__title">Payload resumido</div>
                        </div>
                        <div className="card__body">
                            <CodeBlock>{payload}</CodeBlock>
                            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-3)' }}>
                                Correlation ID: <span className="mono">{run.correlation_id}</span>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </Drawer>
    );
}
