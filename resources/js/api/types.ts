/**
 * Contratos de datos — fuente: Guía Técnica §4-§5 + Plan Maestro §04.
 * Estos enums son un conjunto CERRADO compartido con el backend.
 * Agregar un valor exige tocar backend, frontend y la tabla de estados del doc de diseño.
 */

export type AgentStatus = 'online' | 'offline' | 'enrolled' | 'disabled';
export type RunStatus = 'pending' | 'success' | 'running' | 'failed' | 'skipped' | 'stopping' | 'interrupted';
export type CommandStatus = 'pending' | 'claimed' | 'completed' | 'failed' | 'expired' | 'skipped';
export type SyncStatus = 'enabled' | 'paused' | 'disabled';
export type ClientHealth = 'ok' | 'warning' | 'error' | 'enrolled';
export type TriggerType = 'schedule' | 'manual' | 'command';
export type CommandType = 'run_now' | 'stop_run' | 'pause_sync' | 'resume_sync' | 'refresh_config' | 'inspect_source_table';
export type AuditKind = 'command' | 'event' | 'error' | 'config' | 'auth';

/** Clave de estado admitida por el sistema visual único (lib/status.ts). */
export type StatusKey =
    | AgentStatus
    | RunStatus
    | CommandStatus
    | SyncStatus
    | ClientHealth;

// ---------------------------------------------------------------- listados

export interface ListResponse<T> {
    data: T[];
    page: number;
    page_size: number;
    total: number;
}

export interface ApiErrorBody {
    error: { code: string; message: string };
}

// ---------------------------------------------------------------- agente

export interface AgentListItem {
    code: string;
    client: string;
    machine: string;
    version: string;
    status: AgentStatus;
    last_heartbeat: string | null; // ISO 8601 UTC
    ip: string;
    syncs_count: number;
    last_error: string | null;
}

export interface AgentSyncAssignment {
    code: string;
    name: string;
    source: {
        database_engine: string;
        system_name: string;
        system_version: string;
    };
    interval_seconds: number;
    status: SyncStatus;
}

export interface AgentTimelineItem {
    type: string;
    detail: string;
    at: string;
}

export interface AgentDetail extends AgentListItem {
    config: {
        interval_seconds: number;
        batch_size: number;
        endpoint: string;
        tls: string;
        log_level: string;
    };
    outbox: { pending: number; sent: number; last_sent: string | null };
    syncs: AgentSyncAssignment[];
    commands: Command[];
    runs: RunListItem[];
    timeline: AgentTimelineItem[];
}

// ---------------------------------------------------------------- run

export interface RunListItem {
    id: string;
    client: string;
    agent: string;
    sync: string;
    status: RunStatus;
    trigger: TriggerType;
    started_at: string;
    ended_at: string | null;
    rows_read: number;
    rows_inserted: number;
    rows_updated: number;
    rows_failed: number;
    error: string | null;
    reviewed_at: string | null;
    reviewed_by: number | null;
}

export interface RunTimelineItem {
    event: string;
    detail: string;
    at: string;
}

export interface RunDetail extends RunListItem {
    correlation_id: string;
    timeline: RunTimelineItem[];
    /** Detalle técnico del error (stack/driver), solo si failed. */
    tech_message?: string | null;
}

// ---------------------------------------------------------------- comando

export interface Command {
    id: string;
    type: CommandType;
    agent: string;
    by: string;
    created_at: string;
    status: CommandStatus;
    result: Record<string, unknown> | string | null;
    expires_at: string;
    /** Presente en stop_run / run_now cuando aplica. */
    sync_code?: string | null;
    run_id?: string | null;
}

export interface SourceInspectionColumn {
    name: string;
    type: string;
    sample: string | number | boolean | null;
}

export interface SourceInspectionResult {
    driver: 'firebird' | 'sqlserver';
    profile_ref: string;
    schema: string | null;
    table: string;
    position: number;
    has_row: boolean;
    has_next: boolean;
    columns: SourceInspectionColumn[];
    error_code?: string;
    message?: string;
}

// ---------------------------------------------------------------- cliente

export interface ClientListItem {
    id: number;
    name: string;
    system: string;
    agents: number;
    syncs: number;
    health: ClientHealth;
    health_reason: string | null;
    last_sync: string | null;
    open_errors: number;
}

export interface ClientDetail extends ClientListItem {
    agents_list: AgentListItem[];
    runs: RunListItem[];
    /** Últimas ejecuciones fallidas, separadas del historial general para explicar la salud Error. */
    errors: RunListItem[];
}

// ---------------------------------------------------------------- catálogo

export interface SyncCatalogItem {
    name: string;
    code: string;
    direction: 'read' | 'write';
    source_id: number | null;
    source: string;
    min_version: string;
    enabled: boolean;
    key: string;
    desc: string;
    interval_seconds: number;
}

export type UpdateSyncInput = Partial<Pick<SyncCatalogItem,
    'name' | 'source_id' | 'min_version' | 'enabled' | 'key' | 'desc' | 'interval_seconds'
>>;

export interface ReadRecipeInput {
    schema_version: '1.0';
    recipe_code: string;
    engine: 'declarative_table_reader';
    minimum_agent_version: string;
    source: {
        profile_ref: string;
        driver: 'firebird' | 'sqlserver';
        schema?: string;
        table: string;
        columns: string[];
    };
    scope?: {
        where: {
            operator: 'date_window';
            column: string;
            window: 'current_calendar_year';
        };
    };
    target: {
        profile_ref: 'bapps_mysql';
        table: string;
        strategy: 'full_snapshot' | 'daily_history_v1';
        ownership: 'create_new' | 'managed_only';
        key_columns?: string[];
    };
    constants?: Record<string, string | number | boolean | null>;
    transformations?: Array<'profit.article_tax_rate_v1'>;
    limits: {
        batch_rows: number;
        statement_timeout_seconds: number;
        max_runtime_seconds: number;
    };
}

export interface WriteRecipeInput {
    schema_version: '1.0';
    recipe_code: string;
    engine: 'valery_prs_writer_v1';
    minimum_agent_version: string;
    direction: 'write';
    source: { kind: 'bapps_orders_api' };
    target: {
        profile_ref: string;
        driver: 'firebird';
        header_table: 'VENTAS';
        detail_table: 'VENTAS_DETALLES';
        detail_text_table: 'VENTAS_DETALLES_EXT';
    };
    settings: {
        currency_code: '02';
        payment_days: 15;
        document_type: 'PRS';
        max_collision_retries: 5;
        price_tolerance_percent: number;
    };
    limits: {
        claim_limit: 1;
        lease_seconds: number;
        max_runtime_seconds: number;
    };
}

export type CreateSyncInput = Omit<SyncCatalogItem, 'enabled' | 'source'> & {
    enabled?: boolean;
    recipe?: ReadRecipeInput | WriteRecipeInput;
};

export interface SyncSource {
    id: number;
    system_name: string | null;
    system_version: string | null;
    database_engine: string;
    label: string;
    enabled: boolean;
    syncs_count: number;
}

// ---------------------------------------------------------------- auditoría

export interface AuditEvent {
    id: string;
    kind: AuditKind;
    action: string;
    actor: string;
    target: string;
    ctx: string;
    result: string;
    at: string;
}

// ---------------------------------------------------------------- dashboard

export interface DashboardMetrics {
    agents_total: number;
    agents_delta_week: number;
    agents_online: number;
    agents_offline: number;
    syncs_active: number;
    failed_runs_24h: number;
    audit_events_24h: number;
    recent_agents: AgentListItem[];
    recent_audit: AuditEvent[];
    recent_runs: RunListItem[];
    assigned_syncs: {
        code: string;
        client: string;
        interval_seconds: number;
        status: SyncStatus | RunStatus;
    }[];
}

// ---------------------------------------------------------------- auth

export interface LoginResponse {
    token: string;
    user: { name: string; email: string; role: string };
}
