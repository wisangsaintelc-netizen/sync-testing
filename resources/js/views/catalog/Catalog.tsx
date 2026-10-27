import { useEffect, useMemo, useState } from 'react';
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
    createSync,
    createSyncSource,
    deleteSync,
    deleteSyncSource,
    getAgentCommand,
    getAgents,
    getSyncSources,
    getSyncs,
    inspectSourceTable,
    patchSync,
    patchSyncSource,
} from '@/api/endpoints';
import { ApiError } from '@/api/client';
import type { CreateSyncInput, SourceInspectionColumn, SourceInspectionResult, SyncCatalogItem, SyncSource, UpdateSyncInput } from '@/api/types';
import { DataTable } from '@/components/DataTable';
import { ConfirmDialog } from '@/components/ConfirmDialog';
import { Drawer } from '@/components/Drawer';
import { FilterBar } from '@/components/FilterBar';
import { IntervalInput } from '@/components/IntervalInput';
import { Notice } from '@/components/Notice';
import { StatusBadge } from '@/components/StatusBadge';
import { useToast } from '@/components/Toast';
import { CardsSkeleton, EmptyState, ErrorState } from '@/components/states';
import { IconPlus } from '@/components/icons';
import { intervalLabel } from '@/lib/format';
import { useListView } from '@/lib/useListView';

const CHIPS = [
    { value: '', label: 'Todos' },
    { value: 'enabled', label: 'Habilitados' },
    { value: 'disabled', label: 'Deshabilitados' },
];

type SyncForm = {
    direction: 'read' | 'write';
    name: string;
    code: string;
    source_id: number;
    min_version: string;
    key: string;
    desc: string;
    interval_seconds: number;
    source_profile_ref: string;
    source_schema: string;
    source_table: string;
    source_columns: string;
    target_table: string;
    strategy: 'full_snapshot' | 'daily_history_v1';
    ownership: 'create_new' | 'managed_only';
    key_columns: string;
    date_filter_enabled: boolean;
    date_filter_column: string;
    batch_rows: number;
    statement_timeout_seconds: number;
    max_runtime_seconds: number;
    price_tolerance_percent: number;
};

type CatalogEditForm = Pick<SyncCatalogItem,
    'name' | 'source_id' | 'min_version' | 'enabled' | 'key' | 'desc' | 'interval_seconds'
>;

const EMPTY_FORM: SyncForm = {
    direction: 'read',
    name: '',
    code: '',
    source_id: 0,
    min_version: '0.6.4',
    key: '',
    desc: '',
    interval_seconds: 900,
    source_profile_ref: 'default',
    source_schema: 'dbo',
    source_table: '',
    source_columns: '',
    target_table: '',
    strategy: 'full_snapshot',
    ownership: 'create_new',
    key_columns: '',
    date_filter_enabled: false,
    date_filter_column: '',
    batch_rows: 1000,
    statement_timeout_seconds: 60,
    max_runtime_seconds: 3600,
    price_tolerance_percent: 5,
};

const EMPTY_SOURCE = {
    system_name: '',
    system_version: '',
    database_engine: '',
};

function parseIdentifiers(value: string): string[] {
    return [...new Set(value.split(/[\s,;]+/).map((item) => item.trim()).filter(Boolean))];
}

function recipeDriver(databaseEngine: string): 'firebird' | 'sqlserver' | null {
    const normalized = databaseEngine.toLowerCase().replaceAll(/\s+/g, '');
    if (normalized.includes('firebird')) return 'firebird';
    if (normalized.includes('sqlserver')) return 'sqlserver';
    return null;
}

function versionAtLeast(actual: string, minimum: string): boolean {
    const current = actual.split('.').map((part) => Number(part));
    const required = minimum.split('.').map((part) => Number(part));
    for (let index = 0; index < Math.max(current.length, required.length); index += 1) {
        const left = current[index] ?? 0;
        const right = required[index] ?? 0;
        if (left > right) return true;
        if (left < right) return false;
    }
    return true;
}

function sampleLabel(value: SourceInspectionColumn['sample']): string {
    if (value === null) return 'NULL';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return String(value);
}

function canonicalSyncCode(value: string): string {
    return value.trim().toLowerCase();
}

function catalogEditForm(sync: SyncCatalogItem): CatalogEditForm {
    return {
        name: sync.name,
        source_id: sync.source_id,
        min_version: sync.min_version,
        enabled: sync.enabled,
        key: sync.key,
        desc: sync.desc,
        interval_seconds: sync.interval_seconds,
    };
}

function createPayload(form: SyncForm, source: SyncSource | undefined): CreateSyncInput {
    if (!source) throw new Error('Selecciona una fuente habilitada.');
    const driver = recipeDriver(source.database_engine);
    if (!driver) throw new Error('La fuente seleccionada debe usar Firebird o SQL Server.');
    if (form.direction === 'write') {
        if (driver !== 'firebird') throw new Error('El escritor de presupuestos Valery requiere Firebird.');
        return {
            name: form.name.trim(),
            code: canonicalSyncCode(form.code),
            direction: 'write',
            source_id: form.source_id,
            min_version: form.min_version.trim(),
            key: form.key.trim(),
            desc: form.desc.trim(),
            interval_seconds: form.interval_seconds,
            recipe: {
                schema_version: '1.0',
                recipe_code: canonicalSyncCode(form.code),
                engine: 'valery_prs_writer_v1',
                minimum_agent_version: form.min_version.trim(),
                direction: 'write',
                source: { kind: 'bapps_orders_api' },
                target: {
                    profile_ref: form.source_profile_ref.trim(),
                    driver: 'firebird',
                    header_table: 'VENTAS',
                    detail_table: 'VENTAS_DETALLES',
                    detail_text_table: 'VENTAS_DETALLES_EXT',
                },
                settings: {
                    currency_code: '02',
                    payment_days: 15,
                    document_type: 'PRS',
                    max_collision_retries: 5,
                    price_tolerance_percent: form.price_tolerance_percent,
                },
                limits: { claim_limit: 1, lease_seconds: 300, max_runtime_seconds: 1800 },
            },
        };
    }
    const columns = parseIdentifiers(form.source_columns);
    const keyColumns = parseIdentifiers(form.key_columns);
    const sourceRecipe = {
        profile_ref: form.source_profile_ref.trim(),
        driver,
        ...(driver === 'sqlserver' ? { schema: form.source_schema.trim() } : {}),
        table: form.source_table.trim(),
        columns,
    };

    return {
        name: form.name.trim(),
        code: canonicalSyncCode(form.code),
        direction: 'read',
        source_id: form.source_id,
        min_version: form.min_version.trim(),
        key: form.key.trim(),
        desc: form.desc.trim(),
        interval_seconds: form.interval_seconds,
        recipe: {
            schema_version: '1.0',
            recipe_code: canonicalSyncCode(form.code),
            engine: 'declarative_table_reader',
            minimum_agent_version: form.min_version.trim(),
            source: sourceRecipe,
            ...(form.date_filter_enabled ? {
                scope: {
                    where: {
                        operator: 'date_window',
                        column: form.date_filter_column.trim(),
                        window: 'current_calendar_year',
                    },
                },
            } : {}),
            target: {
                profile_ref: 'bapps_mysql',
                table: form.target_table.trim(),
                strategy: form.strategy,
                ownership: form.ownership,
                ...(keyColumns.length ? { key_columns: keyColumns } : {}),
            },
            limits: {
                batch_rows: form.batch_rows,
                statement_timeout_seconds: form.statement_timeout_seconds,
                max_runtime_seconds: form.max_runtime_seconds,
            },
        },
    };
}

export function Catalog() {
    const { search, onSearch, chip, onChip } = useListView();
    const queryClient = useQueryClient();
    const toast = useToast();
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [createStep, setCreateStep] = useState<1 | 2>(1);
    const [sourcesOpen, setSourcesOpen] = useState(false);
    const [form, setForm] = useState(EMPTY_FORM);
    const [sourceForm, setSourceForm] = useState(EMPTY_SOURCE);
    const [editingSource, setEditingSource] = useState<SyncSource | null>(null);
    const [editingSourceForm, setEditingSourceForm] = useState(EMPTY_SOURCE);
    const [editingCatalog, setEditingCatalog] = useState<SyncCatalogItem | null>(null);
    const [editingCatalogForm, setEditingCatalogForm] = useState<CatalogEditForm | null>(null);
    const [catalogPendingDeletion, setCatalogPendingDeletion] = useState<SyncCatalogItem | null>(null);
    const [formError, setFormError] = useState<string | null>(null);
    const [sourceError, setSourceError] = useState<string | null>(null);
    const [catalogError, setCatalogError] = useState<string | null>(null);
    const [inspectionAgent, setInspectionAgent] = useState('');
    const [inspectionCommandId, setInspectionCommandId] = useState<string | null>(null);
    const [inspectionError, setInspectionError] = useState<string | null>(null);
    const [inspectionPosition, setInspectionPosition] = useState(1);
    const [inspectionInitialized, setInspectionInitialized] = useState(false);

    const query = useQuery({
        queryKey: ['syncs', { chip, search }],
        queryFn: () => getSyncs({ page_size: 100, status: chip || undefined, search: search || undefined }),
        placeholderData: keepPreviousData,
    });
    const sourcesQuery = useQuery({
        queryKey: ['sync-sources'],
        queryFn: () => getSyncSources({ page_size: 100 }),
    });
    const selectedSource = sourcesQuery.data?.data.find((source) => source.id === form.source_id);
    const sourceDriver = selectedSource ? recipeDriver(selectedSource.database_engine) : null;
    const agentsQuery = useQuery({
        queryKey: ['agents', 'source-inspection'],
        queryFn: () => getAgents({ page_size: 100, status: 'online' }),
        enabled: drawerOpen && createStep === 2,
        refetchInterval: 30_000,
    });
    const inspectionQuery = useQuery({
        queryKey: ['source-inspection', inspectionAgent, inspectionCommandId],
        queryFn: () => getAgentCommand(inspectionAgent, inspectionCommandId!),
        enabled: Boolean(inspectionAgent && inspectionCommandId),
        refetchInterval: (result) => {
            const status = result.state.data?.status;
            return status === 'pending' || status === 'claimed' ? 1_000 : false;
        },
    });
    const inspectionResult = inspectionQuery.data?.status === 'completed'
        ? inspectionQuery.data.result as SourceInspectionResult | null
        : null;

    useEffect(() => {
        const command = inspectionQuery.data;
        if (!command) return;
        if (command.status === 'completed' && command.result?.columns) {
            const result = command.result as unknown as SourceInspectionResult;
            if (!inspectionInitialized) {
                setForm((current) => ({
                    ...current,
                    source_columns: result.columns.map((column) => column.name).join('\n'),
                }));
                setInspectionInitialized(true);
            }
            setInspectionError(null);
        } else if (command.status === 'failed' || command.status === 'expired' || command.status === 'skipped') {
            const result = command.result as SourceInspectionResult | null;
            setInspectionError(result?.message || result?.error_code || `La inspección terminó con estado ${command.status}.`);
        }
    }, [inspectionInitialized, inspectionQuery.data]);

    const create = useMutation({
        mutationFn: () => createSync(createPayload(form, selectedSource)),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            setDrawerOpen(false);
            setCreateStep(1);
            setForm(EMPTY_FORM);
            setFormError(null);
            toast.success('Sincronizador creado correctamente.');
        },
        onError: (error) => {
            const message = error instanceof ApiError
                ? `${error.code}: ${error.message}`
                : error instanceof Error ? error.message : 'No se pudo crear el sincronizador.';
            setFormError(message);
            toast.error(message);
        },
    });
    const inspect = useMutation({
        mutationFn: (position: number) => {
            if (!inspectionAgent || !sourceDriver) {
                throw new Error('Selecciona un agente online compatible.');
            }
            return inspectSourceTable(inspectionAgent, {
                profile_ref: form.source_profile_ref.trim(),
                driver: sourceDriver,
                ...(sourceDriver === 'sqlserver' ? { schema: form.source_schema.trim() || 'dbo' } : {}),
                table: form.source_table.trim(),
                position,
            });
        },
        onMutate: (position) => {
            setInspectionPosition(position);
        },
        onSuccess: (command) => {
            setInspectionCommandId(command.id);
            setInspectionError(null);
        },
        onError: (error) => {
            const message = error instanceof ApiError
                ? `${error.code}: ${error.message}`
                : error instanceof Error ? error.message : 'No se pudo solicitar la inspección.';
            setInspectionError(message);
        },
    });
    const createSource = useMutation({
        mutationFn: () => createSyncSource({
            ...sourceForm,
            system_version: sourceForm.system_version || null,
        }),
        onSuccess: (source) => {
            void queryClient.invalidateQueries({ queryKey: ['sync-sources'] });
            setForm((current) => ({ ...current, source_id: source.id }));
            setSourceForm(EMPTY_SOURCE);
            setSourceError(null);
            toast.success('Fuente creada correctamente.');
        },
        onError: (error) => {
            const message = error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo guardar la fuente.';
            setSourceError(message);
            toast.error(message);
        },
    });
    const toggle = useMutation({
        mutationFn: (item: SyncCatalogItem) => patchSync(item.code, { enabled: !item.enabled }),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            toast.success('Estado del sincronizador actualizado.');
        },
        onError: () => toast.error('No se pudo actualizar el sincronizador.'),
    });
    const updateCatalog = useMutation({
        mutationFn: () => {
            if (!editingCatalog || !editingCatalogForm) throw new Error('No hay un sincronizador seleccionado.');
            const payload: UpdateSyncInput = {
                name: editingCatalogForm.name.trim(),
                min_version: editingCatalogForm.min_version.trim(),
                enabled: editingCatalogForm.enabled,
                key: editingCatalogForm.key.trim(),
                desc: editingCatalogForm.desc.trim(),
                interval_seconds: editingCatalogForm.interval_seconds,
            };
            if (editingCatalogForm.source_id !== editingCatalog.source_id) {
                payload.source_id = editingCatalogForm.source_id;
            }
            return patchSync(editingCatalog.code, payload);
        },
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            setEditingCatalog(null);
            setEditingCatalogForm(null);
            setCatalogError(null);
            toast.success('Catálogo actualizado correctamente.');
        },
        onError: (error) => {
            const message = error instanceof ApiError
                ? `${error.code}: ${error.message}`
                : error instanceof Error ? error.message : 'No se pudo actualizar el catálogo.';
            setCatalogError(message);
            toast.error(message);
        },
    });
    const removeCatalog = useMutation({
        mutationFn: (sync: SyncCatalogItem) => deleteSync(sync.code),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            void queryClient.invalidateQueries({ queryKey: ['agents'] });
            void queryClient.invalidateQueries({ queryKey: ['agent'] });
            setCatalogPendingDeletion(null);
            toast.success('Sincronizador eliminado y asignaciones retiradas.');
        },
        onError: (error) => {
            const message = error instanceof ApiError
                ? `${error.code}: ${error.message}`
                : 'No se pudo eliminar el sincronizador.';
            toast.error(message);
        },
    });
    const toggleSource = useMutation({
        mutationFn: (source: SyncSource) => patchSyncSource(source.id, { enabled: !source.enabled }),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['sync-sources'] });
            setSourceError(null);
            toast.success('Estado de la fuente actualizado.');
        },
        onError: (error) => {
            const message = error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo actualizar la fuente.';
            setSourceError(message);
            toast.error(message);
        },
    });
    const updateSource = useMutation({
        mutationFn: () => patchSyncSource(editingSource!.id, {
            ...editingSourceForm,
            system_version: editingSourceForm.system_version || null,
        }),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['sync-sources'] });
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            setEditingSource(null);
            setSourceError(null);
            toast.success('Cambios guardados correctamente.');
        },
        onError: (error) => {
            const message = error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo editar la fuente.';
            setSourceError(message);
            toast.error(message);
        },
    });
    const deleteSource = useMutation({
        mutationFn: (source: SyncSource) => deleteSyncSource(source.id),
        onSuccess: () => {
            void queryClient.invalidateQueries({ queryKey: ['sync-sources'] });
            void queryClient.invalidateQueries({ queryKey: ['syncs'] });
            setSourceError(null);
            toast.success('Fuente eliminada correctamente.');
        },
        onError: (error) => {
            const message = error instanceof ApiError ? `${error.code}: ${error.message}` : 'No se pudo eliminar la fuente.';
            setSourceError(message);
            toast.error(message);
        },
    });

    const groups = useMemo(() => {
        const map = new Map<string, SyncCatalogItem[]>();
        query.data?.data.forEach((sync) => map.set(sync.source, [...(map.get(sync.source) ?? []), sync]));
        return [...map.entries()];
    }, [query.data]);
    const enabledSources = sourcesQuery.data?.data.filter((source) => source.enabled) ?? [];
    const catalogSources = sourcesQuery.data?.data ?? [];
    const setText = (key: 'name' | 'code' | 'min_version' | 'key' | 'desc' | 'source_profile_ref' | 'source_schema' | 'source_columns' | 'target_table' | 'key_columns' | 'date_filter_column') =>
        (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
            setForm((current) => ({ ...current, [key]: key === 'code' ? canonicalSyncCode(event.target.value) : event.target.value }));
    const closeCreateDrawer = () => {
        setDrawerOpen(false);
        setCreateStep(1);
        setFormError(null);
        setInspectionAgent('');
        setInspectionCommandId(null);
        setInspectionError(null);
        setInspectionPosition(1);
        setInspectionInitialized(false);
    };
    const closeCatalogEditDrawer = () => {
        if (updateCatalog.isPending) return;
        setEditingCatalog(null);
        setEditingCatalogForm(null);
        setCatalogError(null);
    };
    const onlineAgents = agentsQuery.data?.data ?? [];
    const selectedColumns = new Set(parseIdentifiers(form.source_columns));
    const inspectionPending = inspect.isPending
        || inspectionQuery.data?.status === 'pending'
        || inspectionQuery.data?.status === 'claimed';
    const resetInspection = () => {
        setInspectionCommandId(null);
        setInspectionError(null);
        setInspectionPosition(1);
        setInspectionInitialized(false);
    };
    const toggleInspectionColumn = (column: string) => {
        setForm((current) => {
            const selected = new Set(parseIdentifiers(current.source_columns));
            if (selected.has(column)) selected.delete(column);
            else selected.add(column);
            return { ...current, source_columns: [...selected].join('\n') };
        });
    };
    const canContinue = Boolean(form.name.trim() && form.code.trim() && form.source_id && form.min_version.trim() && form.key.trim());
    const canCreate = form.direction === 'write' ? Boolean(
        canContinue
        && sourceDriver === 'firebird'
        && form.source_profile_ref.trim(),
    ) : Boolean(
        canContinue
        && sourceDriver
        && form.source_profile_ref.trim()
        && form.source_table.trim()
        && parseIdentifiers(form.source_columns).length
        && form.target_table.trim()
        && (!form.date_filter_enabled || form.date_filter_column.trim())
        && (form.strategy !== 'daily_history_v1' || parseIdentifiers(form.key_columns).length),
    );

    return (
        <>
            <div className="row" style={{ marginBottom: 0 }}>
                <div className="grow">
                    <FilterBar
                        searchValue={search}
                        onSearch={onSearch}
                        searchPlaceholder="nombre, código o fuente…"
                        chips={CHIPS}
                        activeChip={chip}
                        onChip={onChip}
                        count={query.data ? `${query.data.total} sincronizadores` : undefined}
                    />
                </div>
                <button className="btn btn--secondary" style={{ marginBottom: 14 }} onClick={() => setSourcesOpen(true)}>
                    Gestionar fuentes
                </button>
                <button className="btn btn--primary" style={{ marginBottom: 14 }} onClick={() => {
                    setDrawerOpen(true);
                    setCreateStep(1);
                    setInspectionAgent('');
                    setInspectionCommandId(null);
                    setInspectionError(null);
                    setInspectionPosition(1);
                    setInspectionInitialized(false);
                }}>
                    <IconPlus size={13} /> Nuevo sync
                </button>
            </div>

            {query.isPending && <CardsSkeleton cards={6} />}
            {query.isError && <div className="card"><ErrorState error={query.error} onRetry={() => void query.refetch()} /></div>}
            {query.data && query.data.data.length === 0 && <div className="card"><EmptyState title="Sin sincronizadores" hint="Crea uno con el botón Nuevo sync." /></div>}

            {groups.map(([source, syncs]) => (
                <section key={source} style={{ marginBottom: 24 }}>
                    <div className="row" style={{ marginBottom: 9 }}>
                        <div className="kicker">Fuente</div>
                        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-strong)' }}>{source}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{syncs.length} sincronizador{syncs.length === 1 ? '' : 'es'}</div>
                    </div>
                    <div className="card-grid">
                        {syncs.map((sync) => <CatalogCard
                            key={sync.code}
                            sync={sync}
                            pending={toggle.isPending || updateCatalog.isPending || removeCatalog.isPending}
                            onToggle={() => toggle.mutate(sync)}
                            onEdit={() => {
                                setEditingCatalog(sync);
                                setEditingCatalogForm(catalogEditForm(sync));
                                setCatalogError(null);
                            }}
                            onDelete={() => setCatalogPendingDeletion(sync)}
                        />)}
                    </div>
                </section>
            ))}

            <ConfirmDialog
                open={catalogPendingDeletion !== null}
                title="Eliminar sincronizador"
                confirmLabel="Eliminar sincronizador"
                busy={removeCatalog.isPending}
                onCancel={() => setCatalogPendingDeletion(null)}
                onConfirm={() => { if (catalogPendingDeletion) removeCatalog.mutate(catalogPendingDeletion); }}
            >
                <p>Vas a retirar <strong>{catalogPendingDeletion?.name}</strong> de todos los agentes asignados.</p>
                <p>El catálogo desaparecerá del Centro; el historial de ejecuciones y la auditoría se conservarán.</p>
            </ConfirmDialog>

            <Drawer
                open={drawerOpen}
                onClose={closeCreateDrawer}
                code="Nuevo sincronizador"
                name={createStep === 1 ? 'Definición en el catálogo global' : form.direction === 'read' ? 'Receta de lectura y publicación' : 'Escritor de presupuestos Valery'}
                actions={<>
                    {createStep === 1 ? (
                        <button className="btn btn--accent btn--sm" disabled={!canContinue} onClick={() => { setFormError(null); setCreateStep(2); }}>Continuar</button>
                    ) : <>
                        <button className="btn btn--ghost-light btn--sm" disabled={create.isPending} onClick={() => setCreateStep(1)}>Atrás</button>
                        <button className="btn btn--accent btn--sm" disabled={create.isPending || !canCreate} onClick={() => create.mutate()}>{create.isPending ? 'Creando y publicando…' : 'Crear y publicar'}</button>
                    </>}
                    <button className="btn btn--ghost-light btn--sm" disabled={create.isPending} onClick={closeCreateDrawer}>Cancelar</button>
                </>}
            >
                <div className="row" style={{ marginBottom: 12 }}>
                    <span className={`status-badge ${createStep === 1 ? 'status-badge--running' : ''}`}>1 · Identidad</span>
                    <span style={{ color: 'var(--text-3)' }}>›</span>
                    <span className={`status-badge ${createStep === 2 ? 'status-badge--running' : ''}`}>2 · {form.direction === 'read' ? 'Lectura y destino' : 'Escritura segura'}</span>
                </div>
                <Notice>{createStep === 1
                    ? 'El código técnico es inmutable. En el siguiente paso se publicará la primera versión firmada de la receta.'
                    : 'La receta solo admite identificadores y opciones controladas: nunca se descarga SQL ni código ejecutable al agente.'}
                </Notice>
                {formError && <div className="login-error mono">{formError}</div>}
                {createStep === 1 ? (
                    <div className="card card--nested"><div className="card__body stack">
                        <Field label="Nombre legible"><input value={form.name} onChange={setText('name')} placeholder="Nombre del sincronizador" /></Field>
                        <Field label="Código técnico"><input className="mono" value={form.code} onChange={setText('code')} placeholder="productos_terminados" /><div className="field__hint">Minúsculas, números y guion bajo; se normaliza automáticamente.</div></Field>
                        <Field label="Dirección">
                            <select value={form.direction} onChange={(event) => setForm((current) => ({
                                ...current,
                                direction: event.target.value as SyncForm['direction'],
                                min_version: event.target.value === 'write' ? '0.7.0' : current.min_version,
                                key: event.target.value === 'write' && !current.key ? 'order_code' : current.key,
                            }))}>
                                <option value="read">Lectura · sistema administrativo hacia MySQL BAPPS</option>
                                <option value="write">Escritura · pedidos BAPPS hacia Valery</option>
                            </select>
                        </Field>
                        <Field label="Fuente">
                            <select value={form.source_id} onChange={(event) => setForm((current) => ({ ...current, source_id: Number(event.target.value) }))}>
                                <option value={0}>Selecciona una fuente…</option>
                                {enabledSources.map((source) => <option value={source.id} key={source.id}>{source.label}</option>)}
                            </select>
                        </Field>
                        {enabledSources.length === 0 && <div className="field__error">Crea y habilita una fuente antes de registrar un sincronizador.</div>}
                        {selectedSource && !sourceDriver && <div className="field__error">Esta fuente no es compatible. Use Firebird o SQL Server.</div>}
                        {form.direction === 'write' && selectedSource && sourceDriver !== 'firebird' && <div className="field__error">La escritura de PRS requiere Valery sobre Firebird.</div>}
                        <div className="row">
                            <Field label="Versión mínima del agente" grow><input className="mono" value={form.min_version} onChange={setText('min_version')} placeholder="0.6.3" /></Field>
                            <Field label="Frecuencia de ejecución" grow><IntervalInput seconds={form.interval_seconds} onChange={(interval_seconds) => setForm((current) => ({ ...current, interval_seconds }))} /></Field>
                        </div>
                        <Field label="Clave funcional"><input className="mono" value={form.key} onChange={setText('key')} placeholder="co_cli" /></Field>
                        <Field label="Descripción"><textarea rows={3} value={form.desc} onChange={setText('desc')} placeholder="Qué sincroniza y desde dónde." /></Field>
                    </div></div>
                ) : (
                    <div className="stack">
                        {form.direction === 'write' ? (
                            <div className="card card--nested"><div className="card__body stack">
                                <div className="kicker">Motor empaquetado · valery_prs_writer_v1</div>
                                <Notice>Creará VENTAS, VENTAS_DETALLES y VENTAS_DETALLES_EXT en una transacción. No acepta SQL libre ni modifica inventarios.</Notice>
                                <div className="row">
                                    <Field label="Perfil Firebird local" grow><input className="mono" value={form.source_profile_ref} onChange={(event) => setForm((current) => ({ ...current, source_profile_ref: event.target.value }))} /></Field>
                                    <Field label="Moneda" grow><input className="mono" value="02 · USD" readOnly /></Field>
                                </div>
                                <div className="row">
                                    <Field label="Tipo de documento" grow><input className="mono" value="PRS" readOnly /></Field>
                                    <Field label="Vencimiento" grow><input value="15 días desde la creación del pedido" readOnly /></Field>
                                </div>
                                <Field label="Tolerancia de precio (%)"><input className="mono" type="number" min={0} max={100} step={0.1} value={form.price_tolerance_percent} onChange={(event) => setForm((current) => ({ ...current, price_tolerance_percent: Number(event.target.value) }))} /></Field>
                                <details>
                                    <summary className="kicker" style={{ cursor: 'pointer' }}>Tablas permitidas</summary>
                                    <div className="mono" style={{ marginTop: 10 }}>VENTAS · VENTAS_DETALLES · VENTAS_DETALLES_EXT · MONEDA · CLIENTES · VENDEDORES · PRODUCTOS_FACTURABLES</div>
                                </details>
                            </div></div>
                        ) : (<>
                        <div className="card card--nested"><div className="card__body stack">
                            <div className="kicker">Origen · {selectedSource?.label}</div>
                            <Field label="Agente online para inspección">
                                <select value={inspectionAgent} onChange={(event) => {
                                    setInspectionAgent(event.target.value);
                                    resetInspection();
                                }}>
                                    <option value="">Selecciona el agente que tiene acceso a esta base…</option>
                                    {onlineAgents.map((agent) => {
                                        const compatible = versionAtLeast(agent.version, '0.6.4');
                                        return (
                                            <option value={agent.code} key={agent.code} disabled={!compatible}>
                                                {agent.code} · {agent.machine} · v{agent.version}{compatible ? '' : ' (requiere 0.6.4)'}
                                            </option>
                                        );
                                    })}
                                </select>
                            </Field>
                            {agentsQuery.isPending && <div style={{ fontSize: 11, color: 'var(--text-3)' }}>Buscando agentes online…</div>}
                            {agentsQuery.data && onlineAgents.length === 0 && <div className="field__error">No hay agentes online disponibles para consultar la fuente.</div>}
                            <div className="row">
                                <Field label="Perfil local del agente" grow><input className="mono" value={form.source_profile_ref} onChange={(event) => {
                                    setForm((current) => ({ ...current, source_profile_ref: event.target.value }));
                                    resetInspection();
                                }} placeholder="default" /></Field>
                                <Field label="Motor" grow><input className="mono" value={sourceDriver ?? 'No compatible'} readOnly /></Field>
                            </div>
                            {sourceDriver === 'sqlserver' && <Field label="Esquema"><input className="mono" value={form.source_schema} onChange={(event) => {
                                setForm((current) => ({ ...current, source_schema: event.target.value }));
                                resetInspection();
                            }} placeholder="dbo" /></Field>}
                            <div className="row" style={{ alignItems: 'flex-end' }}>
                                <Field label="Tabla origen" grow>
                                    <input
                                        className="mono"
                                        value={form.source_table}
                                        onChange={(event) => {
                                            setForm((current) => ({
                                                ...current,
                                                source_table: event.target.value,
                                                source_columns: '',
                                                target_table: current.target_table || event.target.value,
                                            }));
                                            resetInspection();
                                        }}
                                        placeholder={sourceDriver === 'firebird' ? 'CLIENTES' : 'clientes'}
                                    />
                                </Field>
                                <button
                                    className="btn btn--primary"
                                    disabled={!inspectionAgent || !sourceDriver || !form.source_profile_ref.trim() || !form.source_table.trim() || inspectionPending}
                                    onClick={() => inspect.mutate(1)}
                                >
                                    {inspectionPending ? 'Consultando agente…' : 'Consultar tabla'}
                                </button>
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--text-3)' }}>
                                El agente lee como máximo dos filas: el registro solicitado y una referencia para habilitar “siguiente”. Las credenciales permanecen protegidas en la máquina.
                            </div>
                            {inspectionError && <div className="login-error mono">{inspectionError}</div>}
                            {inspectionResult && (
                                <div className="card card--nested">
                                    <div className="card__header">
                                        <div>
                                            <div className="card__title">{inspectionResult.columns.length} campos encontrados</div>
                                            <div style={{ fontSize: 10.5, color: 'var(--text-3)' }}>
                                                {inspectionResult.has_row ? `Valores del registro ${inspectionResult.position}` : `No existe el registro ${inspectionResult.position}; se muestran sus campos`}
                                            </div>
                                        </div>
                                        <div className="row" style={{ marginBottom: 0 }}>
                                            <button className="btn btn--secondary btn--sm" onClick={() => setForm((current) => ({
                                                ...current,
                                                source_columns: inspectionResult.columns.map((column) => column.name).join('\n'),
                                            }))}>Todos</button>
                                            <button className="btn btn--secondary btn--sm" onClick={() => setForm((current) => ({
                                                ...current,
                                                source_columns: '',
                                            }))}>Ninguno</button>
                                        </div>
                                    </div>
                                    <div className="row" style={{ marginBottom: 12, alignItems: 'flex-end', justifyContent: 'space-between' }}>
                                        <div className="row" style={{ marginBottom: 0 }}>
                                            <button
                                                className="btn btn--secondary btn--sm"
                                                disabled={inspectionPending || inspectionResult.position <= 1}
                                                onClick={() => inspect.mutate(inspectionResult.position - 1)}
                                                aria-label="Ver registro anterior"
                                            >‹ Anterior</button>
                                            <button
                                                className="btn btn--secondary btn--sm"
                                                disabled={inspectionPending || !inspectionResult.has_row || !inspectionResult.has_next}
                                                onClick={() => inspect.mutate(inspectionResult.position + 1)}
                                                aria-label="Ver siguiente registro"
                                            >Siguiente ›</button>
                                        </div>
                                        <label className="field" style={{ width: 138, marginBottom: 0 }}>
                                            <span className="field__label">Ir al registro</span>
                                            <input
                                                className="mono"
                                                type="number"
                                                min={1}
                                                max={10000}
                                                value={inspectionPosition}
                                                onChange={(event) => setInspectionPosition(Math.max(1, Math.min(10000, Number(event.target.value) || 1)))}
                                                onKeyDown={(event) => {
                                                    if (event.key === 'Enter') inspect.mutate(inspectionPosition);
                                                }}
                                                aria-label="Posición del registro"
                                            />
                                        </label>
                                        <button
                                            className="btn btn--secondary btn--sm"
                                            disabled={inspectionPending}
                                            onClick={() => inspect.mutate(inspectionPosition)}
                                        >Ir</button>
                                    </div>
                                    <DataTable
                                        rows={inspectionResult.columns}
                                        rowKey={(column) => column.name}
                                        columns={[
                                            {
                                                key: 'selected',
                                                header: 'Usar',
                                                render: (column) => (
                                                    <input
                                                        type="checkbox"
                                                        checked={selectedColumns.has(column.name)}
                                                        onChange={() => toggleInspectionColumn(column.name)}
                                                        aria-label={`Incluir ${column.name}`}
                                                    />
                                                ),
                                            },
                                            { key: 'name', header: 'Campo', render: (column) => <span className="cell-id">{column.name}</span> },
                                            { key: 'type', header: 'Tipo', render: (column) => <span className="cell-mono">{column.type}</span> },
                                            { key: 'sample', header: 'Valor', render: (column) => <span className="cell-mono">{sampleLabel(column.sample)}</span> },
                                        ]}
                                    />
                                </div>
                            )}
                            {!inspectionResult && !inspectionPending && (
                                <Notice>Selecciona un agente online, escribe la tabla y pulsa “Consultar tabla” para elegir sus campos sin salir del Centro.</Notice>
                            )}
                            <label className="row" style={{ justifyContent: 'flex-start' }}>
                                <input type="checkbox" checked={form.date_filter_enabled} onChange={(event) => setForm((current) => ({ ...current, date_filter_enabled: event.target.checked }))} />
                                <span>Leer solamente registros del año calendario actual</span>
                            </label>
                            {form.date_filter_enabled && <Field label="Columna de fecha">
                                {inspectionResult ? (
                                    <select value={form.date_filter_column} onChange={(event) => setForm((current) => ({ ...current, date_filter_column: event.target.value }))}>
                                        <option value="">Selecciona el campo de fecha…</option>
                                        {inspectionResult.columns.map((column) => <option value={column.name} key={column.name}>{column.name}</option>)}
                                    </select>
                                ) : <input className="mono" value={form.date_filter_column} onChange={setText('date_filter_column')} placeholder="fec_emis" />}
                            </Field>}
                        </div></div>

                        <div className="card card--nested"><div className="card__body stack">
                            <div className="kicker">Destino · MySQL BAPPS</div>
                            <Field label="Tabla destino"><input className="mono" value={form.target_table} onChange={setText('target_table')} placeholder="CLIENTES" /></Field>
                            <div className="row">
                                <Field label="Estrategia" grow>
                                    <select value={form.strategy} onChange={(event) => setForm((current) => ({ ...current, strategy: event.target.value as SyncForm['strategy'] }))}>
                                        <option value="full_snapshot">Fotografía completa con reemplazo</option>
                                        <option value="daily_history_v1">Histórico diario</option>
                                    </select>
                                </Field>
                                <Field label="Propiedad de tabla" grow>
                                    <select value={form.ownership} onChange={(event) => setForm((current) => ({ ...current, ownership: event.target.value as SyncForm['ownership'] }))}>
                                        <option value="create_new">Crear nueva tabla administrada</option>
                                        <option value="managed_only">Usar solo si ya pertenece a BAPPS Sync</option>
                                    </select>
                                </Field>
                            </div>
                            {form.strategy === 'daily_history_v1' && <Field label="Columnas clave del histórico"><input className="mono" value={form.key_columns} onChange={setText('key_columns')} placeholder="co_cli" /></Field>}
                            <details>
                                <summary className="kicker" style={{ cursor: 'pointer' }}>Límites operativos</summary>
                                <div className="row" style={{ marginTop: 12 }}>
                                    <Field label="Filas por lote" grow><input className="mono" type="number" min={100} max={5000} value={form.batch_rows} onChange={(event) => setForm((current) => ({ ...current, batch_rows: Number(event.target.value) }))} /></Field>
                                    <Field label="Timeout SQL (s)" grow><input className="mono" type="number" min={5} max={600} value={form.statement_timeout_seconds} onChange={(event) => setForm((current) => ({ ...current, statement_timeout_seconds: Number(event.target.value) }))} /></Field>
                                    <Field label="Duración máxima (s)" grow><input className="mono" type="number" min={30} max={21600} value={form.max_runtime_seconds} onChange={(event) => setForm((current) => ({ ...current, max_runtime_seconds: Number(event.target.value) }))} /></Field>
                                </div>
                            </details>
                        </div></div>
                        </>)}
                    </div>
                )}
            </Drawer>

            <Drawer
                open={Boolean(editingCatalog && editingCatalogForm)}
                onClose={closeCatalogEditDrawer}
                code={editingCatalog?.code ?? 'Editar sincronizador'}
                name="Editar catálogo de sincronizador"
                actions={<>
                    <button
                        className="btn btn--accent btn--sm"
                        disabled={updateCatalog.isPending || !editingCatalogForm?.name.trim() || !editingCatalogForm.min_version.trim() || !editingCatalogForm.key.trim()}
                        onClick={() => updateCatalog.mutate()}
                    >{updateCatalog.isPending ? 'Guardando…' : 'Guardar cambios'}</button>
                    <button className="btn btn--ghost-light btn--sm" disabled={updateCatalog.isPending} onClick={closeCatalogEditDrawer}>Cancelar</button>
                </>}
            >
                <Notice>El código técnico no se puede cambiar porque identifica el sincronizador en los agentes y sus asignaciones. Para cambiar tabla, columnas, destino o estrategia se debe publicar una nueva versión de la receta.</Notice>
                {catalogError && <div className="login-error mono">{catalogError}</div>}
                {editingCatalogForm && <div className="card card--nested"><div className="card__body stack">
                    <Field label="Código técnico"><input className="mono" value={editingCatalog?.code ?? ''} readOnly /></Field>
                    <Field label="Nombre legible"><input value={editingCatalogForm.name} onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, name: event.target.value } : current)} /></Field>
                    <Field label="Fuente">
                        <select
                            value={editingCatalogForm.source_id ?? ''}
                            onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, source_id: Number(event.target.value) } : current)}
                        >
                            {editingCatalogForm.source_id === null && <option value="" disabled>Sin fuente configurada</option>}
                            {catalogSources.map((source) => (
                                <option
                                    key={source.id}
                                    value={source.id}
                                    disabled={!source.enabled && source.id !== editingCatalogForm.source_id}
                                >{source.label}{source.enabled ? '' : ' (deshabilitada)'}</option>
                            ))}
                        </select>
                    </Field>
                    {catalogSources.length === 0 && <div className="field__error">No hay fuentes disponibles para este catálogo.</div>}
                    <div className="row">
                        <Field label="Versión mínima del agente" grow><input className="mono" value={editingCatalogForm.min_version} onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, min_version: event.target.value } : current)} /></Field>
                        <Field label="Frecuencia de ejecución" grow><IntervalInput seconds={editingCatalogForm.interval_seconds} onChange={(interval_seconds) => setEditingCatalogForm((current) => current ? { ...current, interval_seconds } : current)} /></Field>
                    </div>
                    <Field label="Clave funcional"><input className="mono" value={editingCatalogForm.key} onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, key: event.target.value } : current)} /></Field>
                    <Field label="Descripción"><textarea rows={4} value={editingCatalogForm.desc} onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, desc: event.target.value } : current)} /></Field>
                    <label className="row" style={{ justifyContent: 'flex-start' }}>
                        <input type="checkbox" checked={editingCatalogForm.enabled} onChange={(event) => setEditingCatalogForm((current) => current ? { ...current, enabled: event.target.checked } : current)} />
                        <span>Habilitado globalmente</span>
                    </label>
                </div></div>}
            </Drawer>

            <Drawer
                open={sourcesOpen}
                onClose={() => setSourcesOpen(false)}
                code="Fuentes de sincronización"
                name="Sistema administrativo, versión y base de datos"
                actions={<button className="btn btn--ghost-light btn--sm" onClick={() => setSourcesOpen(false)}>Cerrar</button>}
            >
                <Notice>Registra el sistema administrativo, su versión y el motor de base de datos que identifican el origen compatible.</Notice>
                {sourceError && <div className="login-error mono">{sourceError}</div>}
                <div className="card card--nested" style={{ marginTop: 14 }}><div className="card__body stack">
                    <div className="row">
                        <Field label="Sistema administrativo" grow><input value={sourceForm.system_name} onChange={(event) => setSourceForm((current) => ({ ...current, system_name: event.target.value }))} placeholder="Nombre del sistema (opcional)" /></Field>
                        <Field label="Versión del sistema" grow><input value={sourceForm.system_version} onChange={(event) => setSourceForm((current) => ({ ...current, system_version: event.target.value }))} placeholder="Versión (opcional)" /></Field>
                    </div>
                    <Field label="Base de datos"><input value={sourceForm.database_engine} onChange={(event) => setSourceForm((current) => ({ ...current, database_engine: event.target.value }))} placeholder="Motor de base de datos" /></Field>
                    <button className="btn btn--primary btn--sm" disabled={createSource.isPending || !sourceForm.database_engine} onClick={() => createSource.mutate()}>{createSource.isPending ? 'Guardando…' : 'Agregar fuente'}</button>
                </div></div>
                <div style={{ marginTop: 18 }}>
                    <div className="row" style={{ marginBottom: 9 }}>
                        <div className="kicker">Fuentes existentes</div>
                        {sourcesQuery.data && <div style={{ fontSize: 11, color: 'var(--text-3)' }}>{sourcesQuery.data.total}</div>}
                    </div>
                    {sourcesQuery.isPending && <CardsSkeleton cards={2} />}
                    {sourcesQuery.isError && <div className="card"><ErrorState error={sourcesQuery.error} onRetry={() => void sourcesQuery.refetch()} /></div>}
                    {sourcesQuery.data?.data.length === 0 && <div className="card"><EmptyState title="Aún no hay fuentes registradas" hint="Crea la primera fuente con el formulario anterior." /></div>}
                    {sourcesQuery.data && sourcesQuery.data.data.length > 0 && <div className="stack">
                        {sourcesQuery.data.data.map((source) => editingSource?.id === source.id ? (
                            <div className="card card--nested" key={source.id}><div className="card__body stack">
                                <div className="row"><Field label="Sistema administrativo" grow><input value={editingSourceForm.system_name} onChange={(event) => setEditingSourceForm((current) => ({ ...current, system_name: event.target.value }))} /></Field><Field label="Versión del sistema" grow><input value={editingSourceForm.system_version} onChange={(event) => setEditingSourceForm((current) => ({ ...current, system_version: event.target.value }))} /></Field></div>
                                <Field label="Base de datos"><input value={editingSourceForm.database_engine} onChange={(event) => setEditingSourceForm((current) => ({ ...current, database_engine: event.target.value }))} /></Field>
                                <div className="row"><button className="btn btn--primary btn--sm" disabled={updateSource.isPending || !editingSourceForm.database_engine} onClick={() => updateSource.mutate()}>{updateSource.isPending ? 'Guardando…' : 'Guardar cambios'}</button><button className="btn btn--secondary btn--sm" onClick={() => setEditingSource(null)}>Cancelar</button></div>
                            </div></div>
                        ) : (
                            <div className="card" key={source.id}><div className="card__body row">
                                <div className="grow"><div style={{ fontWeight: 600 }}>{source.label}</div><div className="mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>{source.database_engine} · {source.syncs_count} sync{source.syncs_count === 1 ? '' : 's'}</div></div>
                                <StatusBadge status={source.enabled ? 'enabled' : 'disabled'} />
                                <button className="btn btn--secondary btn--sm" onClick={() => { setEditingSource(source); setEditingSourceForm({ system_name: source.system_name ?? '', system_version: source.system_version ?? '', database_engine: source.database_engine }); }}>Editar</button>
                                <button className="btn btn--secondary btn--sm" disabled={toggleSource.isPending} onClick={() => toggleSource.mutate(source)}>{source.enabled ? 'Deshabilitar' : 'Habilitar'}</button>
                                <button className="btn btn--danger btn--sm" title={source.syncs_count > 0 ? 'No se puede eliminar mientras tenga sincronizadores asociados.' : 'Eliminar fuente'} disabled={source.syncs_count > 0 || deleteSource.isPending} onClick={() => { if (window.confirm(`¿Eliminar la fuente ${source.label}?`)) deleteSource.mutate(source); }}>Eliminar</button>
                            </div></div>
                        ))}
                    </div>}
                </div>
            </Drawer>
        </>
    );
}

function CatalogCard({ sync, pending, onToggle, onEdit, onDelete }: { sync: SyncCatalogItem; pending: boolean; onToggle: () => void; onEdit: () => void; onDelete: () => void }) {
    return <div className="entity-card entity-card--static">
        <div className="entity-card__top"><div><div className="entity-card__name">{sync.name}</div><div className="entity-card__sub mono">{sync.code}</div></div><span className="entity-card__badge"><StatusBadge status={sync.enabled ? 'enabled' : 'disabled'} /></span></div>
        <div style={{ fontSize: 12, color: 'var(--text-2)', lineHeight: 1.45 }}>{sync.desc}</div>
        <dl className="drawer-kv">
            <div><dt>Dirección</dt><dd>{sync.direction === 'write' ? 'Escritura' : 'Lectura'}</dd></div>
            <div><dt>Versión</dt><dd className="mono">{sync.min_version}</dd></div>
            <div><dt>Frecuencia</dt><dd>{intervalLabel(sync.interval_seconds)}</dd></div>
            <div><dt>Clave</dt><dd className="mono">{sync.key}</dd></div>
        </dl>
        <div className="entity-card__footer"><button className="btn btn--secondary btn--sm" disabled={pending} onClick={onEdit}>Editar</button><button className="btn btn--secondary btn--sm" disabled={pending} onClick={onToggle}>{sync.enabled ? 'Deshabilitar' : 'Habilitar'}</button>{!sync.enabled && <button className="btn btn--danger btn--sm" disabled={pending} onClick={onDelete}>Eliminar</button>}</div>
    </div>;
}

function Field({ label, children, grow = false }: { label: string; children: React.ReactNode; grow?: boolean }) {
    return <div className={`field${grow ? ' grow' : ''}`}><label className="field__label">{label}</label>{children}</div>;
}
