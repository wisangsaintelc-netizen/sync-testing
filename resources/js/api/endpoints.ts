/**
 * Una función tipada por endpoint (Guía Técnica §3).
 * Este archivo ES el contrato que el backend Laravel deberá cumplir.
 */

import { request } from './client';
import type {
    AgentDetail,
    AgentListItem,
    AuditEvent,
    ClientDetail,
    ClientListItem,
    Command,
    CommandType,
    CreateSyncInput,
    DashboardMetrics,
    ListResponse,
    LoginResponse,
    RunDetail,
    RunListItem,
    SyncCatalogItem,
    SyncSource,
    SyncStatus,
    SourceInspectionResult,
    UpdateSyncInput,
} from './types';

export interface ListParams {
    page?: number;
    page_size?: number;
    status?: string;
    search?: string;
    [key: string]: string | number | undefined;
}

// ---- auth
export const login = (email: string, password: string) =>
    request<LoginResponse>('/auth/login', { method: 'POST', body: { email, password } });

// ---- dashboard
export const getDashboardMetrics = () => request<DashboardMetrics>('/dashboard/metrics');

// ---- agentes
export const getAgents = (params?: ListParams) =>
    request<ListResponse<AgentListItem>>('/agents', { params });

export const getAgent = (code: string) => request<AgentDetail>(`/agents/${code}`);

export const sendAgentCommand = (code: string, type: CommandType, payload?: { sync_code?: string; run_id?: string }) =>
    request<Command>(`/agents/${code}/commands`, { method: 'POST', body: { type, ...payload } });

export const inspectSourceTable = (
    code: string,
    body: { profile_ref: string; driver: 'firebird' | 'sqlserver'; schema?: string; table: string; position: number },
) => request<Command>(`/agents/${code}/commands`, {
    method: 'POST',
    body: { type: 'inspect_source_table', ...body },
});

export const getAgentCommand = (code: string, commandId: string) =>
    request<Omit<Command, 'result'> & { result: SourceInspectionResult | null }>(`/agents/${code}/commands/${commandId}`);

export const patchAgentSync = (
    code: string,
    syncCode: string,
    body: { status?: SyncStatus; interval_seconds?: number },
) => request<AgentDetail>(`/agents/${code}/syncs/${syncCode}`, { method: 'PATCH', body });

export const assignAgentSync = (
    code: string,
    body: {
        sync_code: string;
        status: SyncStatus;
        interval_seconds: number;
        config?: {
            profile_ref: string;
            warehouse_code: string;
            station_code: string;
            user_code: string;
            server_code: string;
            orders_api_url: string;
        };
        secrets?: { orders_api_token: string };
    },
) => request<AgentDetail>(`/agents/${code}/syncs`, { method: 'POST', body });

// ---- runs
export const getRuns = (params?: ListParams) =>
    request<ListResponse<RunListItem>>('/runs', { params });

export const getRun = (id: string) => request<RunDetail>(`/runs/${id}`);

export const retryRun = (id: string) =>
    request<RunListItem>(`/runs/${id}/retry`, { method: 'POST' });

export const reviewRun = (id: string) =>
    request<RunListItem>(`/runs/${id}/review`, { method: 'POST' });

// ---- auditoría
export const getAudit = (params?: ListParams) =>
    request<ListResponse<AuditEvent>>('/audit', { params });

// ---- clientes
export const getClients = (params?: ListParams) =>
    request<ListResponse<ClientListItem>>('/clients', { params });

export const getClient = (id: number) => request<ClientDetail>(`/clients/${id}`);

// ---- catálogo
export const getSyncs = (params?: ListParams) =>
    request<ListResponse<SyncCatalogItem>>('/syncs', { params });

export const createSync = (body: CreateSyncInput) =>
    request<SyncCatalogItem>('/syncs', { method: 'POST', body });

export const patchSync = (code: string, body: UpdateSyncInput) =>
    request<SyncCatalogItem>(`/syncs/${code}`, { method: 'PATCH', body });

export const deleteSync = (code: string) =>
    request<void>(`/syncs/${code}`, { method: 'DELETE' });

export const getSyncSources = (params?: ListParams) =>
    request<ListResponse<SyncSource>>('/sync-sources', { params });

export const createSyncSource = (body: Omit<SyncSource, 'id' | 'label' | 'enabled' | 'syncs_count'> & { enabled?: boolean }) =>
    request<SyncSource>('/sync-sources', { method: 'POST', body });

export const patchSyncSource = (id: number, body: Partial<SyncSource>) =>
    request<SyncSource>(`/sync-sources/${id}`, { method: 'PATCH', body });

export const deleteSyncSource = (id: number) =>
    request<void>(`/sync-sources/${id}`, { method: 'DELETE' });
