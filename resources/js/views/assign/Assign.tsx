import { useMemo, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { assignAgentSync, getAgent, getAgents, getSyncs, patchAgentSync } from '@/api/endpoints';
import { ApiError } from '@/api/client';
import type { AgentSyncAssignment, SyncCatalogItem, SyncStatus } from '@/api/types';
import { Card } from '@/components/Card';
import { FilterBar } from '@/components/FilterBar';
import { Notice } from '@/components/Notice';
import { IntervalInput } from '@/components/IntervalInput';
import { StatusBadge } from '@/components/StatusBadge';
import { useToast } from '@/components/Toast';
import { CardsSkeleton, EmptyState, ErrorState, TableSkeleton } from '@/components/states';
import { relativeTime } from '@/lib/format';
import { useListView } from '@/lib/useListView';

/**
 * Flujo de 2 pasos (no colapsar en uno):
 *  Paso 0 — grilla de selección de agente.
 *  Paso 1 — tabla de permisos del agente con "Cambiar agente" para volver.
 */
export function Assign() {
    const { agentCode } = useParams<{ agentCode: string }>();
    const navigate = useNavigate();

    return agentCode === undefined ? (
        <StepPickAgent onPick={(code) => navigate(`/agents/assign/${encodeURIComponent(code)}`)} />
    ) : (
        <StepPermissions agentCode={agentCode} onBack={() => navigate('/agents/assign')} />
    );
}

function StepPickAgent({ onPick }: { onPick: (code: string) => void }) {
    const { search, onSearch } = useListView();

    const query = useQuery({
        queryKey: ['agents', { assign: true, search }],
        queryFn: () => getAgents({ page_size: 100, search: search || undefined }),
        placeholderData: keepPreviousData,
    });

    return (
        <div className="assign-step">
            <div className="assign-header">
                <span className="step-pill">Paso 1 de 2</span>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-strong)' }}>
                    Selecciona el agente a configurar
                </div>
            </div>

            <FilterBar
                searchValue={search}
                onSearch={onSearch}
                searchPlaceholder="código, cliente o máquina…"
                count={query.data ? `${query.data.total} agentes` : undefined}
            />

            {query.isPending && <CardsSkeleton cards={8} />}
            {query.isError && (
                <div className="card">
                    <ErrorState error={query.error} onRetry={() => void query.refetch()} />
                </div>
            )}
            {query.data && query.data.data.length === 0 && (
                <div className="card">
                    <EmptyState title="Sin agentes que coincidan" />
                </div>
            )}
            {query.data && query.data.data.length > 0 && (
                <div className="card-grid">
                    {query.data.data.map((a) => (
                        <div className="entity-card" key={a.code} onClick={() => onPick(a.code)}>
                            <div className="entity-card__top">
                                <div>
                                    <div className="entity-card__name mono" style={{ color: 'var(--deep-blue)' }}>{a.code}</div>
                                    <div className="entity-card__sub">{a.client}</div>
                                </div>
                                <span className="entity-card__badge">
                                    <StatusBadge status={a.status} />
                                </span>
                            </div>
                            <div className="entity-card__footer">
                                <span className="mono">{a.machine}</span>
                                <span style={{ marginLeft: 'auto' }}>
                                    {a.syncs_count} syncs · {relativeTime(a.last_heartbeat)}
                                </span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

interface RowEdit {
    status: SyncStatus;
    interval: number;
}

interface SyncVersionGroup {
    version: string;
    syncs: AgentSyncAssignment[];
}

interface SyncSystemGroup {
    name: string;
    versions: SyncVersionGroup[];
}

interface SyncDatabaseGroup {
    engine: string;
    systems: SyncSystemGroup[];
}

function groupSyncs(syncs: AgentSyncAssignment[]): SyncDatabaseGroup[] {
    const databases = new Map<string, Map<string, Map<string, AgentSyncAssignment[]>>>();

    for (const sync of syncs) {
        const { database_engine: engine, system_name: system, system_version: version } = sync.source;
        const systems = databases.get(engine) ?? new Map<string, Map<string, AgentSyncAssignment[]>>();
        const versions = systems.get(system) ?? new Map<string, AgentSyncAssignment[]>();
        const assignments = versions.get(version) ?? [];

        assignments.push(sync);
        versions.set(version, assignments);
        systems.set(system, versions);
        databases.set(engine, systems);
    }

    return [...databases.entries()]
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([engine, systems]) => ({
            engine,
            systems: [...systems.entries()]
                .sort(([left], [right]) => left.localeCompare(right))
                .map(([name, versions]) => ({
                    name,
                    versions: [...versions.entries()]
                        .sort(([left], [right]) => left.localeCompare(right))
                        .map(([version, assignments]) => ({
                            version,
                            syncs: [...assignments].sort((left, right) => left.name.localeCompare(right.name)),
                        })),
                })),
        }));
}

function StepPermissions({ agentCode, onBack }: { agentCode: string; onBack: () => void }) {
    const queryClient = useQueryClient();
    const toast = useToast();
    const [edits, setEdits] = useState<Record<string, RowEdit>>({});
    const [rowError, setRowError] = useState<Record<string, string>>({});
    const [addOpen, setAddOpen] = useState(false);
    const [addCode, setAddCode] = useState('');
    const [addStatus, setAddStatus] = useState<SyncStatus>('enabled');
    const [addInterval, setAddInterval] = useState(900);
    const [addError, setAddError] = useState<string | null>(null);
    const [writerConfig, setWriterConfig] = useState({
        profile_ref: 'default',
        warehouse_code: '01',
        station_code: 'GERENCIA',
        user_code: 'GERENCIA',
        server_code: '00',
        orders_api_url: '',
        orders_api_token: '',
    });

    const query = useQuery({
        queryKey: ['agent', agentCode],
        queryFn: () => getAgent(agentCode),
    });
    const catalogQuery = useQuery({
        queryKey: ['syncs', 'assignment-options'],
        queryFn: () => getSyncs({ page_size: 100, status: 'enabled' }),
        enabled: addOpen,
    });

    const save = useMutation({
        mutationFn: (args: { syncCode: string; body: { status?: SyncStatus; interval_seconds?: number } }) =>
            patchAgentSync(agentCode, args.syncCode, args.body),
        onSuccess: (_, args) => {
            void queryClient.invalidateQueries({ queryKey: ['agent', agentCode] });
            void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
            setEdits((e) => {
                const { [args.syncCode]: _drop, ...rest } = e;
                return rest;
            });
            setRowError((e) => ({ ...e, [args.syncCode]: '' }));
            toast.success(`Configuración de ${args.syncCode} actualizada.`);
        },
        onError: (err, args) => {
            const message = err instanceof ApiError ? `${err.code}: ${err.message}` : 'No se pudo guardar la configuración.';
            setRowError((e) => ({
                ...e,
                [args.syncCode]: message,
            }));
            toast.error(message);
        },
    });
    const selectedCatalog = (catalogQuery.data?.data ?? []).find((sync) => sync.code === addCode);
    const assign = useMutation({
        mutationFn: (syncCode: string) => assignAgentSync(agentCode, {
            sync_code: syncCode,
            status: addStatus,
            interval_seconds: addInterval,
            ...(selectedCatalog?.direction === 'write' ? {
                config: {
                    profile_ref: writerConfig.profile_ref,
                    warehouse_code: writerConfig.warehouse_code,
                    station_code: writerConfig.station_code,
                    user_code: writerConfig.user_code,
                    server_code: writerConfig.server_code,
                    orders_api_url: writerConfig.orders_api_url,
                },
                secrets: { orders_api_token: writerConfig.orders_api_token },
            } : {}),
        }),
        onSuccess: (_, syncCode) => {
            void queryClient.invalidateQueries({ queryKey: ['agent', agentCode] });
            void queryClient.invalidateQueries({ queryKey: ['agents'] });
            void queryClient.invalidateQueries({ queryKey: ['dashboard'] });
            setAddOpen(false);
            setAddCode('');
            setAddStatus('enabled');
            setWriterConfig((current) => ({ ...current, orders_api_token: '' }));
            setAddError(null);
            toast.success(`Sincronizador ${syncCode} asignado a ${agentCode}.`);
        },
        onError: (error) => {
            const message = error instanceof ApiError
                ? `${error.code}: ${error.message}`
                : 'No se pudo asignar el sincronizador.';
            setAddError(message);
            toast.error(message);
        },
    });

    const agent = query.data;
    const groupedSyncs = useMemo(() => groupSyncs(agent?.syncs ?? []), [agent?.syncs]);
    const availableSyncs = useMemo(() => {
        const assigned = new Set(agent?.syncs.map((sync) => sync.code) ?? []);
        return (catalogQuery.data?.data ?? []).filter((sync) => !assigned.has(sync.code));
    }, [agent?.syncs, catalogQuery.data?.data]);
    const selectedAvailableCatalog = availableSyncs.find((sync) => sync.code === addCode);
    const openAssign = () => {
        setAddOpen(true);
        setAddError(null);
    };
    const selectCatalog = (sync: SyncCatalogItem | undefined) => {
        setAddCode(sync?.code ?? '');
        if (sync) setAddInterval(sync.interval_seconds);
    };

    const editOf = (code: string): RowEdit | undefined => edits[code];

    return (
        <div className="assign-step">
            <div className="assign-header">
                <span className="step-pill">Paso 2 de 2</span>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-strong)' }}>
                    Permisos e intervalos de <span className="mono" style={{ color: 'var(--deep-blue)' }}>{agentCode}</span>
                    {agent && <span style={{ color: 'var(--text-2b)', fontWeight: 500 }}> · {agent.client}</span>}
                </div>
                <button className="btn btn--secondary btn--sm" style={{ marginLeft: 'auto' }} onClick={onBack}>
                    Cambiar agente
                </button>
                <button className="btn btn--primary btn--sm" onClick={openAssign}>
                    Agregar sync
                </button>
            </div>

            <Notice>
                Pausar un sync impide sus futuras ejecuciones (la ejecución activa no se detiene — usa “Detener” en la
                ejecución). Los cambios de intervalo los descarga el agente en su próximo ciclo de configuración.
            </Notice>

            {addOpen && (
                <div className="card card--nested" style={{ marginBottom: 14 }}>
                    <div className="card__body stack">
                        <div className="row" style={{ marginBottom: 0 }}>
                            <div>
                                <div className="kicker">Catálogo global</div>
                                <div className="card__title">Asignar sincronizador a este agente</div>
                            </div>
                            <button className="btn btn--secondary btn--sm" style={{ marginLeft: 'auto' }} onClick={() => setAddOpen(false)}>
                                Cancelar
                            </button>
                        </div>
                        <div className="row" style={{ alignItems: 'flex-end', marginBottom: 0 }}>
                            <div className="field grow">
                                <label className="field__label" htmlFor="assign-sync-code">Sincronizador habilitado</label>
                                <select
                                    id="assign-sync-code"
                                    value={addCode}
                                    onChange={(event) => selectCatalog(availableSyncs.find((sync) => sync.code === event.target.value))}
                                >
                                    <option value="">Selecciona un sincronizador…</option>
                                    {availableSyncs.map((sync) => (
                                        <option value={sync.code} key={sync.code}>{sync.name} · {sync.code}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="field" style={{ width: 148 }}>
                                <label className="field__label" htmlFor="assign-status">Estado inicial</label>
                                <select id="assign-status" value={addStatus} onChange={(event) => setAddStatus(event.target.value as SyncStatus)}>
                                    <option value="enabled">Habilitado</option>
                                    <option value="paused">Pausado</option>
                                    <option value="disabled">Deshabilitado</option>
                                </select>
                            </div>
                            <div className="field" style={{ width: 210 }}>
                                <span className="field__label">Frecuencia</span>
                                <IntervalInput seconds={addInterval} onChange={setAddInterval} />
                            </div>
                            <button
                                className="btn btn--primary btn--sm"
                                disabled={
                                    !addCode
                                    || assign.isPending
                                    || (selectedAvailableCatalog?.direction === 'write'
                                        && (!writerConfig.orders_api_url.trim() || !writerConfig.orders_api_token.trim()))
                                }
                                onClick={() => assign.mutate(addCode)}
                            >
                                {assign.isPending ? 'Asignando…' : 'Asignar'}
                            </button>
                        </div>
                        {catalogQuery.isPending && <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Cargando catálogo habilitado…</div>}
                        {availableSyncs.length === 0 && !catalogQuery.isPending && <div className="field__error">No hay sincronizadores habilitados pendientes de asignación.</div>}
                        {selectedAvailableCatalog && <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{selectedAvailableCatalog.source} · {selectedAvailableCatalog.direction === 'write' ? 'Escritura' : 'Lectura'} · requiere agente {selectedAvailableCatalog.min_version}</div>}
                        {selectedAvailableCatalog?.direction === 'write' && (
                            <div className="card card--nested"><div className="card__body stack">
                                <div className="kicker">Configuración del escritor Valery</div>
                                <div className="row">
                                    <FieldInput label="Perfil Firebird" value={writerConfig.profile_ref} onChange={(profile_ref) => setWriterConfig((current) => ({ ...current, profile_ref }))} />
                                    <FieldInput label="Depósito" value={writerConfig.warehouse_code} onChange={(warehouse_code) => setWriterConfig((current) => ({ ...current, warehouse_code }))} />
                                    <FieldInput label="Estación" value={writerConfig.station_code} onChange={(station_code) => setWriterConfig((current) => ({ ...current, station_code }))} />
                                </div>
                                <div className="row">
                                    <FieldInput label="Usuario Valery" value={writerConfig.user_code} onChange={(user_code) => setWriterConfig((current) => ({ ...current, user_code }))} />
                                    <FieldInput label="Servidor" value={writerConfig.server_code} onChange={(server_code) => setWriterConfig((current) => ({ ...current, server_code }))} />
                                </div>
                                <FieldInput label="URL API privada de pedidos" value={writerConfig.orders_api_url} onChange={(orders_api_url) => setWriterConfig((current) => ({ ...current, orders_api_url }))} />
                                <div className="field">
                                    <label className="field__label" htmlFor="writer-api-token">Token API por agente</label>
                                    <input id="writer-api-token" type="password" autoComplete="new-password" value={writerConfig.orders_api_token} onChange={(event) => setWriterConfig((current) => ({ ...current, orders_api_token: event.target.value }))} />
                                    <span className="field__hint">Se cifra en el Centro y el agente lo protege con Windows DPAPI.</span>
                                </div>
                            </div></div>
                        )}
                        {addError && <div className="login-error mono">{addError}</div>}
                    </div>
                </div>
            )}

            <Card flush>
                {query.isPending && <TableSkeleton rows={4} cols={5} />}
                {query.isError && <ErrorState error={query.error} onRetry={() => void query.refetch()} />}
                {agent && agent.syncs.length === 0 && (
                    <EmptyState title="Este agente no tiene sincronizadores asignados" />
                )}
                {groupedSyncs.map((database) => (
                    <section key={database.engine} style={{ padding: 14 }}>
                        <div className="row" style={{ marginBottom: 10 }}>
                            <span className="kicker">Base de datos</span>
                            <strong>{database.engine}</strong>
                        </div>
                        <div className="stack">
                            {database.systems.map((system) => (
                                <div className="card card--nested" key={system.name}>
                                    <div className="card__header">
                                        <div>
                                            <div className="kicker">Sistema administrativo</div>
                                            <div className="card__title">{system.name}</div>
                                        </div>
                                    </div>
                                    <div className="card__body--flush stack">
                                        {system.versions.map((version) => (
                                            <div key={version.version}>
                                                <div className="row" style={{ padding: '10px 14px 6px', marginBottom: 0 }}>
                                                    <span className="kicker">Versión del sistema</span>
                                                    <span className="mono" style={{ fontWeight: 600 }}>{version.version}</span>
                                                </div>
                                                <div className="table-wrap">
                                                    <table className="table">
                                                        <thead>
                                                            <tr>
                                                                <th>Sync</th>
                                                                <th>Estado</th>
                                                                <th>Estado nuevo</th>
                                                                <th>Frecuencia</th>
                                                                <th></th>
                                                            </tr>
                                                        </thead>
                                                        <tbody>
                                                            {version.syncs.map((s) => {
                                                                const edit = editOf(s.code) ?? { status: s.status, interval: s.interval_seconds };
                                                                const dirty = edit.status !== s.status || edit.interval !== s.interval_seconds;
                                                                return (
                                                                    <tr key={s.code}>
                                                                        <td>
                                                                            <div className="cell-id">{s.code}</div>
                                                                            <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>{s.name}</div>
                                                                        </td>
                                                                        <td><StatusBadge status={s.status} /></td>
                                                                        <td>
                                                                            <select
                                                                                className="assignment-control"
                                                                                value={edit.status}
                                                                                onChange={(event) => setEdits((current) => ({
                                                                                    ...current,
                                                                                    [s.code]: { ...edit, status: event.target.value as SyncStatus },
                                                                                }))}
                                                                            >
                                                                                <option value="enabled">enabled</option>
                                                                                <option value="paused">paused</option>
                                                                                <option value="disabled">disabled</option>
                                                                            </select>
                                                                        </td>
                                                                        <td>
                                                                            <div style={{ width: 210 }}>
                                                                                <IntervalInput
                                                                                    seconds={edit.interval}
                                                                                    onChange={(interval) => setEdits((current) => ({
                                                                                        ...current,
                                                                                        [s.code]: { ...edit, interval },
                                                                                    }))}
                                                                                />
                                                                            </div>
                                                                        </td>
                                                                        <td>
                                                                            <button
                                                                                className="btn btn--primary btn--sm"
                                                                                disabled={!dirty || save.isPending}
                                                                                onClick={() => save.mutate({
                                                                                    syncCode: s.code,
                                                                                    body: { status: edit.status, interval_seconds: edit.interval },
                                                                                })}
                                                                            >
                                                                                Guardar
                                                                            </button>
                                                                            {rowError[s.code] && (
                                                                                <div className="field__error mono" style={{ marginTop: 4 }}>{rowError[s.code]}</div>
                                                                            )}
                                                                        </td>
                                                                    </tr>
                                                                );
                                                            })}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </section>
                ))}
            </Card>
        </div>
    );
}

function FieldInput({
    label,
    value,
    onChange,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
}) {
    return (
        <div className="field grow">
            <label className="field__label">
                {label}
                <input value={value} onChange={(event) => onChange(event.target.value)} />
            </label>
        </div>
    );
}
