/**
 * Handlers MSW: especificación ejecutable del contrato de la Guía Técnica.
 * Cuando exista el backend Laravel, estos handlers son la referencia de
 * forma exacta de cada request/response (y sus tests).
 *
 * Utilidades de QA (desde la consola del navegador):
 *   localStorage.setItem('bapps_mock_error', '1')  → todos los GET devuelven 500
 *   localStorage.setItem('bapps_mock_empty', '1')  → listados vacíos
 */

import { http, HttpResponse, delay } from 'msw';
import type { DefaultBodyType, PathParams } from 'msw';
import {
    agents,
    audit,
    catalog,
    syncSources,
    clients,
    commands,
    nextCommandId,
    nextRunId,
    pushAudit,
    runs,
} from './db';
import type { AgentRecord, RunRecord } from './db';
import type {
    AgentDetail,
    Command,
    CommandType,
    DashboardMetrics,
    SyncCatalogItem,
    SyncSource,
    SyncStatus,
} from '@/api/types';

const B = '/api/v1';

// ------------------------------------------------------------- helpers

function err(status: number, code: string, message: string) {
    return HttpResponse.json({ error: { code, message } }, { status });
}

function unauthorized(request: Request): Response | null {
    const auth = request.headers.get('Authorization');
    if (!auth?.startsWith('Bearer ')) {
        return err(401, 'UNAUTHENTICATED', 'Token ausente o inválido.');
    }
    return null;
}

function qaFault(): Response | null {
    if (localStorage.getItem('bapps_mock_error')) {
        return err(500, 'INTERNAL_ERROR', 'Fallo simulado del servidor (bapps_mock_error).');
    }
    return null;
}

function paginate<T>(items: T[], url: URL) {
    const page = Math.max(1, Number(url.searchParams.get('page') ?? 1));
    const pageSize = Math.min(200, Math.max(1, Number(url.searchParams.get('page_size') ?? 50)));
    const empty = Boolean(localStorage.getItem('bapps_mock_empty'));
    const source = empty ? [] : items;
    return HttpResponse.json({
        data: source.slice((page - 1) * pageSize, page * pageSize),
        page,
        page_size: pageSize,
        total: source.length,
    });
}

function matches(haystack: (string | null | undefined)[], search: string): boolean {
    const s = search.toLowerCase();
    return haystack.some((h) => h?.toLowerCase().includes(s));
}

function clientResponse(client: (typeof clients)[number]) {
    const { _seed, ...base } = client;
    const clientAgents = agents.filter((agent) => agent.client_id === client.id);
    const clientRuns = runs.filter((run) => run.client_id === client.id);
    const openErrors = clientRuns.filter((run) => run.status === 'failed' && !run.reviewed_at).length;
    const lastSync = clientRuns.map((run) => run.ended_at ?? run.started_at).sort().at(-1) ?? null;
    const health = clientAgents.length === 0
        ? 'enrolled'
        : clientAgents.some((agent) => agent.status !== 'online')
          ? 'warning'
          : 'ok';
    const nonOnlineAgents = clientAgents.filter((agent) => agent.status !== 'online').map((agent) => agent.code);

    return {
        ...base,
        agents: clientAgents.length,
        syncs: clientAgents.reduce((count, agent) => count + agent.syncs_count, 0),
        health,
        health_reason: health === 'warning'
            ? nonOnlineAgents.length === 1
              ? `Agente sin conexión: ${nonOnlineAgents[0]}.`
              : `${nonOnlineAgents.length} agentes sin conexión: ${nonOnlineAgents.join(', ')}.`
            : null,
        last_sync: lastSync,
        open_errors: openErrors,
    };
}

const latency = () => delay(150 + Math.random() * 300);

type Resolver = Parameters<typeof http.get<PathParams, DefaultBodyType>>[1];

/** GET estándar: latencia + auth + fallo QA. */
function guarded(fn: Resolver): Resolver {
    return async (info) => {
        await latency();
        const authFail = unauthorized(info.request);
        if (authFail) return authFail;
        const fault = qaFault();
        if (fault) return fault;
        return fn(info);
    };
}

// ------------------------------------------------------------- transiciones vivas

function finishRun(run: RunRecord, ok: boolean) {
    const endIso = new Date().toISOString();
    if (ok) {
        const read = 400 + Math.floor(Math.random() * 1500);
        run.status = 'success';
        run.rows_read = read;
        run.rows_inserted = Math.floor(read * 0.04);
        run.rows_updated = Math.floor(read * 0.015);
        run.timeline.push({ event: 'run_finished', detail: 'Resultado: success', at: endIso });
    } else {
        run.status = 'failed';
        run.error = 'SOURCE_CONNECTION_FAILED';
        run.tech_message = 'FbException: unable to complete network request to host "localhost". Firebird no responde en el puerto 3050.';
        run.timeline.push({ event: 'sync_error', detail: 'SOURCE_CONNECTION_FAILED', at: endIso });
        const agent = agents.find((a) => a.code === run.agent_code);
        if (agent) agent.last_error = run.error;
    }
    run.ended_at = endIso;
    pushAudit({
        kind: ok ? 'event' : 'error',
        action: ok ? 'run_finished' : 'sync_error',
        actor: 'sistema',
        target: run.agent,
        ctx: run.sync,
        result: ok ? 'success' : (run.error ?? 'failed'),
        at: endIso,
    });
}

function startRun(agent: AgentRecord, syncCode: string, trigger: 'manual' | 'command'): RunRecord {
    const now = new Date().toISOString();
    const run: RunRecord = {
        id: nextRunId(),
        client: agent.client,
        client_id: agent.client_id,
        agent: agent.code,
        agent_code: agent.code,
        sync: syncCode,
        status: 'running',
        trigger,
        started_at: now,
        ended_at: null,
        rows_read: 0,
        rows_inserted: 0,
        rows_updated: 0,
        rows_failed: 0,
        error: null,
        reviewed_at: null,
        reviewed_by: null,
        correlation_id: `corr-${Date.now().toString(36)}`,
        tech_message: null,
        timeline: [{ event: 'run_started', detail: `Trigger: ${trigger}`, at: now }],
    };
    runs.push(run);
    // La ejecución termina sola a los 8–14 s (85% success), como un agente real.
    setTimeout(() => {
        if (run.status === 'running') finishRun(run, Math.random() < 0.85);
    }, 8000 + Math.random() * 6000);
    return run;
}

function completeCommand(cmd: Command, result: string | null = 'OK') {
    cmd.status = 'completed';
    cmd.result = result;
    pushAudit({
        kind: 'command',
        action: `${cmd.type} ejecutado`,
        actor: cmd.by,
        target: cmd.agent,
        ctx: cmd.sync_code ?? '—',
        result: 'completed',
        at: new Date().toISOString(),
    });
}

// ------------------------------------------------------------- handlers

export const handlers = [
    // ---- auth
    http.post(`${B}/auth/login`, async ({ request }) => {
        await latency();
        const body = (await request.json()) as { email?: string; password?: string };
        if (!body?.email || !body?.password) {
            return err(422, 'VALIDATION_FAILED', 'Email y contraseña son obligatorios.');
        }
        if (body.password === 'wrong') {
            return err(401, 'AUTHENTICATION_FAILED', 'Credenciales inválidas.');
        }
        return HttpResponse.json({
            token: `mock-token-${Date.now().toString(36)}`,
            user: { name: 'Soporte BAPPS', email: body.email, role: 'operator' },
        });
    }),

    // ---- dashboard
    http.get(`${B}/dashboard/metrics`, guarded(() => {
        const sortedRuns = [...runs].sort((a, b) => b.started_at.localeCompare(a.started_at));
        const sortedAudit = [...audit].sort((a, b) => b.at.localeCompare(a.at));
        const sortedAgents = [...agents].sort((a, b) => (b.last_heartbeat ?? '').localeCompare(a.last_heartbeat ?? ''));
        const dayAgo = new Date(Date.now() - 86_400_000).toISOString();

        const metrics: DashboardMetrics = {
            agents_total: agents.length,
            agents_delta_week: 3,
            agents_online: agents.filter((a) => a.status === 'online').length,
            agents_offline: agents.filter((a) => a.status === 'offline').length,
            syncs_active: agents.reduce((n, a) => n + a.syncs.filter((s) => s.status === 'enabled').length, 0),
            failed_runs_24h: runs.filter((r) => r.status === 'failed' && !r.reviewed_at && r.started_at >= dayAgo).length,
            audit_events_24h: audit.filter((e) => e.at >= dayAgo).length,
            recent_agents: sortedAgents.slice(0, 5),
            recent_audit: sortedAudit.slice(0, 5),
            recent_runs: sortedRuns.slice(0, 5),
            assigned_syncs: sortedAgents.slice(0, 5).flatMap((a) => {
                const s = a.syncs[0];
                if (!s) return [];
                const runningNow = runs.some((r) => r.agent_code === a.code && r.sync === s.code && r.status === 'running');
                return [{
                    code: s.code,
                    client: a.client,
                    interval_seconds: s.interval_seconds,
                    status: runningNow ? ('running' as const) : s.status,
                }];
            }),
        };
        return HttpResponse.json(metrics);
    })),

    // ---- agentes
    http.get(`${B}/agents`, guarded(({ request }) => {
        const url = new URL(request.url);
        let list = [...agents].sort((a, b) => a.code.localeCompare(b.code));
        const status = url.searchParams.get('status');
        if (status) list = list.filter((a) => a.status === status);
        const search = url.searchParams.get('search');
        if (search) list = list.filter((a) => matches([a.code, a.client, a.machine, a.ip], search));
        return paginate(list, url);
    })),

    http.get(`${B}/agents/:code`, guarded(({ params }) => {
        const agent = agents.find((a) => a.code === params.code);
        if (!agent) return err(404, 'NOT_FOUND', `Agente ${String(params.code)} no existe.`);
        const agentRuns = runs
            .filter((r) => r.agent_code === agent.code)
            .sort((a, b) => b.started_at.localeCompare(a.started_at))
            .slice(0, 8);
        const agentCommands = commands
            .filter((c) => c.agent === agent.code)
            .sort((a, b) => b.created_at.localeCompare(a.created_at))
            .slice(0, 8);
        const timeline = [
            ...(agent.last_heartbeat
                ? [{ type: 'heartbeat', detail: `v${agent.version} · outbox ${agent.outbox.pending}`, at: agent.last_heartbeat }]
                : []),
            ...agentRuns.slice(0, 4).map((r) => ({
                type: r.status === 'failed' ? 'sync_error' : 'run_finished',
                detail: `${r.sync} · ${r.status}`,
                at: r.ended_at ?? r.started_at,
            })),
        ].sort((a, b) => b.at.localeCompare(a.at));

        const detail: AgentDetail = { ...agent, runs: agentRuns, commands: agentCommands, timeline };
        return HttpResponse.json(detail);
    })),

    http.post(`${B}/agents/:code/commands`, guarded(async ({ params, request }) => {
        const agent = agents.find((a) => a.code === params.code);
        if (!agent) return err(404, 'NOT_FOUND', `Agente ${String(params.code)} no existe.`);
        const body = (await request.json()) as { type: CommandType; sync_code?: string; run_id?: string };
        const validTypes: CommandType[] = ['run_now', 'stop_run', 'pause_sync', 'resume_sync', 'refresh_config'];
        if (!validTypes.includes(body.type)) {
            return err(422, 'VALIDATION_FAILED', `type debe ser uno de: ${validTypes.join(', ')}.`);
        }
        if (agent.status === 'offline' || agent.status === 'disabled') {
            // Se acepta igual (el agente lo reclamará al volver), pero run_now sobre disabled se rechaza.
            if (agent.status === 'disabled') return err(409, 'AGENT_DISABLED', 'El agente está deshabilitado.');
        }
        if ((body.type === 'run_now' || body.type === 'pause_sync' || body.type === 'resume_sync') && !body.sync_code) {
            return err(422, 'VALIDATION_FAILED', 'sync_code es obligatorio para este comando.');
        }
        if (body.type === 'stop_run' && !body.run_id) {
            return err(422, 'VALIDATION_FAILED', 'run_id es obligatorio para stop_run.');
        }

        const now = new Date();
        const cmd: Command = {
            id: nextCommandId(),
            type: body.type,
            agent: agent.code,
            by: 'soporte@bapps',
            created_at: now.toISOString(),
            status: 'pending',
            result: null,
            expires_at: new Date(now.getTime() + 7 * 60_000).toISOString(),
            sync_code: body.sync_code ?? null,
            run_id: body.run_id ?? null,
        };
        commands.push(cmd);
        pushAudit({
            kind: 'command',
            action: `${body.type} enviado`,
            actor: cmd.by,
            target: agent.code,
            ctx: body.sync_code ?? body.run_id ?? '—',
            result: 'pending',
            at: cmd.created_at,
        });

        // Simulación del ciclo claim→ejecución del agente.
        const claimDelay = agent.status === 'online' ? 2500 + Math.random() * 2500 : 60_000;
        setTimeout(() => {
            if (cmd.status !== 'pending') return;
            switch (cmd.type) {
                case 'run_now': {
                    const sync = agent.syncs.find((s) => s.code === cmd.sync_code);
                    if (!sync) {
                        cmd.status = 'failed';
                        cmd.result = 'SYNC_NOT_AUTHORIZED';
                        return;
                    }
                    if (sync.status === 'paused') {
                        cmd.status = 'skipped';
                        cmd.result = 'SYNC_PAUSED';
                        return;
                    }
                    const alreadyRunning = runs.some((r) => r.agent_code === agent.code && r.sync === sync.code && r.status === 'running');
                    if (alreadyRunning) {
                        cmd.status = 'skipped';
                        cmd.result = 'SYNC_ALREADY_RUNNING';
                        return;
                    }
                    const run = startRun(agent, sync.code, 'command');
                    completeCommand(cmd, run.id);
                    break;
                }
                case 'stop_run': {
                    const run = runs.find((r) => r.id === cmd.run_id);
                    if (!run || (run.status !== 'running' && run.status !== 'stopping')) {
                        cmd.status = 'skipped';
                        cmd.result = 'RUN_NOT_ACTIVE';
                        return;
                    }
                    run.status = 'stopping';
                    run.timeline.push({ event: 'stop_requested', detail: `stop_run ${cmd.id}`, at: new Date().toISOString() });
                    setTimeout(() => {
                        if (run.status !== 'stopping') return;
                        run.status = 'interrupted';
                        run.ended_at = new Date().toISOString();
                        run.timeline.push({ event: 'run_interrupted', detail: 'Detenida en punto seguro', at: run.ended_at });
                        completeCommand(cmd, run.id);
                    }, 2500 + Math.random() * 2000);
                    break;
                }
                case 'pause_sync':
                case 'resume_sync': {
                    const sync = agent.syncs.find((s) => s.code === cmd.sync_code);
                    if (!sync) {
                        cmd.status = 'failed';
                        cmd.result = 'SYNC_NOT_AUTHORIZED';
                        return;
                    }
                    sync.status = cmd.type === 'pause_sync' ? 'paused' : 'enabled';
                    completeCommand(cmd);
                    break;
                }
                case 'refresh_config':
                    completeCommand(cmd);
                    break;
            }
        }, claimDelay);

        return HttpResponse.json(cmd, { status: 201 });
    })),

    http.patch(`${B}/agents/:code/syncs/:syncCode`, guarded(async ({ params, request }) => {
        const agent = agents.find((a) => a.code === params.code);
        if (!agent) return err(404, 'NOT_FOUND', `Agente ${String(params.code)} no existe.`);
        const sync = agent.syncs.find((s) => s.code === params.syncCode);
        if (!sync) return err(404, 'NOT_FOUND', `Sync ${String(params.syncCode)} no asignado a este agente.`);
        const body = (await request.json()) as { status?: SyncStatus; interval_seconds?: number };
        if (body.interval_seconds !== undefined) {
            if (body.interval_seconds < 60) {
                return err(422, 'INVALID_CONFIG', `interval_seconds debe ser >= 60, se recibió ${body.interval_seconds}.`);
            }
            sync.interval_seconds = body.interval_seconds;
        }
        if (body.status) {
            if (!['enabled', 'paused', 'disabled'].includes(body.status)) {
                return err(422, 'VALIDATION_FAILED', 'status inválido.');
            }
            sync.status = body.status;
        }
        pushAudit({
            kind: 'config',
            action: body.interval_seconds ? 'Intervalo modificado' : `Sync ${body.status}`,
            actor: 'soporte@bapps',
            target: agent.code,
            ctx: sync.code,
            result: 'ok',
            at: new Date().toISOString(),
        });
        agent.syncs_count = agent.syncs.length;
        return HttpResponse.json({ ...agent, runs: [], commands: [], timeline: [] });
    })),

    // ---- runs
    http.get(`${B}/runs`, guarded(({ request }) => {
        const url = new URL(request.url);
        let list = [...runs].sort((a, b) => b.started_at.localeCompare(a.started_at));
        const status = url.searchParams.get('status');
        if (status) list = list.filter((r) => r.status === status);
        const trigger = url.searchParams.get('trigger');
        if (trigger) list = list.filter((r) => r.trigger === trigger);
        const search = url.searchParams.get('search');
        if (search) list = list.filter((r) => matches([r.id, r.client, r.agent, r.sync, r.error], search));
        return paginate(list, url);
    })),

    http.get(`${B}/runs/:id`, guarded(({ params }) => {
        const run = runs.find((r) => r.id === params.id);
        if (!run) return err(404, 'NOT_FOUND', `Ejecución ${String(params.id)} no existe.`);
        return HttpResponse.json(run);
    })),

    http.post(`${B}/runs/:id/retry`, guarded(({ params }) => {
        const run = runs.find((r) => r.id === params.id);
        if (!run) return err(404, 'NOT_FOUND', `Ejecución ${String(params.id)} no existe.`);
        if (run.status !== 'failed') {
            return err(409, 'RUN_NOT_RETRYABLE', 'Solo se puede reintentar una ejecución fallida.');
        }
        const agent = agents.find((a) => a.code === run.agent_code);
        if (!agent) return err(404, 'NOT_FOUND', 'Agente de la ejecución no existe.');
        const newRun = startRun(agent, run.sync, 'manual');
        pushAudit({
            kind: 'command',
            action: 'retry ejecutado',
            actor: 'soporte@bapps',
            target: agent.code,
            ctx: run.sync,
            result: newRun.id,
            at: new Date().toISOString(),
        });
        return HttpResponse.json(newRun, { status: 201 });
    })),

    http.post(`${B}/runs/:id/review`, guarded(({ params }) => {
        const run = runs.find((r) => r.id === params.id);
        if (!run) return err(404, 'NOT_FOUND', `Ejecución ${String(params.id)} no existe.`);
        if (run.status !== 'failed') return err(409, 'REVIEW_REJECTED', 'Solo se pueden revisar ejecuciones fallidas.');

        if (!run.reviewed_at) {
            run.reviewed_at = new Date().toISOString();
            run.reviewed_by = 1;
            pushAudit({
                kind: 'error',
                action: 'review_run',
                actor: 'soporte@bapps',
                target: run.id,
                ctx: run.sync,
                result: 'reviewed',
                at: run.reviewed_at,
            });
        }

        return HttpResponse.json(run);
    })),

    // ---- auditoría
    http.get(`${B}/audit`, guarded(({ request }) => {
        const url = new URL(request.url);
        let list = [...audit].sort((a, b) => b.at.localeCompare(a.at));
        const kind = url.searchParams.get('kind');
        if (kind) list = list.filter((e) => e.kind === kind);
        const search = url.searchParams.get('search');
        if (search) list = list.filter((e) => matches([e.id, e.action, e.actor, e.target, e.ctx, e.result], search));
        return paginate(list, url);
    })),

    // ---- clientes
    http.get(`${B}/clients`, guarded(({ request }) => {
        const url = new URL(request.url);
        let list = clients.map(clientResponse).sort((a, b) => a.name.localeCompare(b.name));
        const health = url.searchParams.get('health') ?? url.searchParams.get('status');
        if (health === 'error') list = list.filter((c) => c.open_errors > 0);
        else if (health) list = list.filter((c) => c.health === health);
        const search = url.searchParams.get('search');
        if (search) list = list.filter((c) => matches([c.name, c.system], search));
        return paginate(list, url);
    })),

    http.get(`${B}/clients/:id`, guarded(({ params }) => {
        const client = clients.find((c) => c.id === Number(params.id));
        if (!client) return err(404, 'NOT_FOUND', `Cliente ${String(params.id)} no existe.`);
        return HttpResponse.json({
            ...clientResponse(client),
            agents_list: agents.filter((a) => a.client_id === client.id),
            runs: runs
                .filter((r) => r.client_id === client.id)
                .sort((a, b) => b.started_at.localeCompare(a.started_at))
                .slice(0, 8),
            errors: runs
                .filter((r) => r.client_id === client.id && r.status === 'failed' && !r.reviewed_at)
                .sort((a, b) => b.started_at.localeCompare(a.started_at))
                .slice(0, 10),
        });
    })),

    // ---- catálogo
    http.get(`${B}/sync-sources`, guarded(({ request }) => paginate(
        syncSources.map((source) => ({ ...source, syncs_count: catalog.filter((sync) => sync.source_id === source.id).length })),
        new URL(request.url),
    ))),

    http.post(`${B}/sync-sources`, guarded(async ({ request }) => {
        const body = (await request.json()) as Partial<SyncSource>;
        if (!body.database_engine) return err(422, 'VALIDATION_FAILED', 'database_engine es obligatorio.');
        const source: SyncSource = {
            id: Math.max(0, ...syncSources.map((item) => item.id)) + 1,
            system_name: body.system_name ?? null,
            system_version: body.system_version ?? null,
            database_engine: body.database_engine,
            label: [body.system_name, body.system_version].filter(Boolean).join(' ') + ` / ${body.database_engine}`,
            enabled: body.enabled ?? true,
            syncs_count: 0,
        };
        syncSources.push(source);
        return HttpResponse.json(source, { status: 201 });
    })),

    http.patch(`${B}/sync-sources/:id`, guarded(async ({ params, request }) => {
        const source = syncSources.find((item) => item.id === Number(params.id));
        if (!source) return err(404, 'NOT_FOUND', 'La fuente no existe.');
        const body = (await request.json()) as Partial<SyncSource>;
        Object.assign(source, body);
        source.label = [source.system_name, source.system_version].filter(Boolean).join(' ') + ` / ${source.database_engine}`;
        return HttpResponse.json(source);
    })),

    http.delete(`${B}/sync-sources/:id`, guarded(({ params }) => {
        const index = syncSources.findIndex((item) => item.id === Number(params.id));
        if (index === -1) return err(404, 'NOT_FOUND', 'La fuente no existe.');
        if (catalog.some((sync) => sync.source_id === Number(params.id))) {
            return err(409, 'SOURCE_IN_USE', 'No se puede eliminar una fuente con sincronizadores asociados.');
        }
        syncSources.splice(index, 1);
        return new HttpResponse(null, { status: 204 });
    })),

    http.get(`${B}/syncs`, guarded(({ request }) => {
        const url = new URL(request.url);
        let list = [...catalog];
        const status = url.searchParams.get('status');
        if (status === 'enabled') list = list.filter((s) => s.enabled);
        if (status === 'disabled') list = list.filter((s) => !s.enabled);
        const search = url.searchParams.get('search');
        if (search) list = list.filter((s) => matches([s.name, s.code, s.source, s.desc], search));
        return paginate(list, url);
    })),

    http.post(`${B}/syncs`, guarded(async ({ request }) => {
        const body = (await request.json()) as Partial<SyncCatalogItem>;
        if (!body.name || !body.code || !body.source_id || !body.key) {
            return err(422, 'VALIDATION_FAILED', 'name, code, source_id y key son obligatorios.');
        }
        if (catalog.some((s) => s.code === body.code)) {
            return err(409, 'DUPLICATE_CODE', `Ya existe un sync con código ${body.code}.`);
        }
        if (!/^\d+\.\d+\.\d+$/.test(body.min_version ?? '')) {
            return err(422, 'VALIDATION_FAILED', 'min_version debe ser semver (ej. 2.4.0).');
        }
        if ((body.interval_seconds ?? 0) < 60) {
            return err(422, 'INVALID_CONFIG', `interval_seconds debe ser >= 60, se recibió ${body.interval_seconds ?? 0}.`);
        }
        const source = syncSources.find((item) => item.id === body.source_id);
        if (!source || !source.enabled) return err(422, 'VALIDATION_FAILED', 'La fuente seleccionada no está habilitada.');
        const item: SyncCatalogItem = {
            name: body.name,
            code: body.code,
            source_id: source.id,
            source: source.label,
            min_version: body.min_version ?? '2.0.0',
            enabled: body.enabled ?? true,
            key: body.key,
            desc: body.desc ?? '',
            interval_seconds: body.interval_seconds ?? 900,
        };
        catalog.push(item);
        pushAudit({
            kind: 'config',
            action: 'Sync creado en catálogo',
            actor: 'soporte@bapps',
            target: item.code,
            ctx: item.source,
            result: 'ok',
            at: new Date().toISOString(),
        });
        return HttpResponse.json(item, { status: 201 });
    })),

    http.patch(`${B}/syncs/:code`, guarded(async ({ params, request }) => {
        const item = catalog.find((s) => s.code === params.code);
        if (!item) return err(404, 'NOT_FOUND', `Sync ${String(params.code)} no existe.`);
        const body = (await request.json()) as Partial<SyncCatalogItem>;
        if (body.interval_seconds !== undefined && body.interval_seconds < 60) {
            return err(422, 'INVALID_CONFIG', `interval_seconds debe ser >= 60, se recibió ${body.interval_seconds}.`);
        }
        const selectedSource = body.source_id === undefined
            ? undefined
            : syncSources.find((source) => source.id === body.source_id);
        if (body.source_id !== undefined && (!selectedSource || !selectedSource.enabled)) {
            return err(422, 'VALIDATION_FAILED', 'La fuente seleccionada no está habilitada.');
        }

        Object.assign(item, {
            ...(body.name !== undefined && { name: body.name }),
            ...(body.desc !== undefined && { desc: body.desc }),
            ...(body.enabled !== undefined && { enabled: body.enabled }),
            ...(body.min_version !== undefined && { min_version: body.min_version }),
            ...(selectedSource && {
                source_id: body.source_id,
                source: selectedSource.label,
            }),
            ...(body.interval_seconds !== undefined && { interval_seconds: body.interval_seconds }),
        });
        pushAudit({
            kind: 'config',
            action: body.enabled === undefined ? 'Sync editado' : body.enabled ? 'Sync habilitado' : 'Sync deshabilitado',
            actor: 'soporte@bapps',
            target: item.code,
            ctx: item.source,
            result: 'ok',
            at: new Date().toISOString(),
        });
        return HttpResponse.json(item);
    })),
];
