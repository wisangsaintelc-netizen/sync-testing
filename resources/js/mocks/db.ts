/**
 * Base de datos en memoria para los mocks.
 * Genera un estado inicial determinista (RNG con semilla) con timestamps
 * relativos a "ahora", y expone mutadores que usan los handlers MSW.
 *
 * Los fixtures visibles en la maqueta standalone están incluidos tal cual
 * (AGT-000142, RUN-8842, etc.) para poder comparar lado a lado.
 */

import type {
    AgentDetail,
    AgentListItem,
    AgentStatus,
    AuditEvent,
    ClientListItem,
    Command,
    CommandType,
    RunDetail,
    RunStatus,
    SyncCatalogItem,
    SyncSource,
    SyncStatus,
    TriggerType,
} from '@/api/types';

// ------------------------------------------------------------------ RNG

let seed = 20260717;
function rnd(): number {
    // mulberry32
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
function pick<T>(arr: readonly T[]): T {
    return arr[Math.floor(rnd() * arr.length)];
}
function int(min: number, max: number): number {
    return min + Math.floor(rnd() * (max - min + 1));
}

const NOW = Date.now();
const iso = (msAgo: number) => new Date(NOW - msAgo).toISOString();

// ------------------------------------------------------------------ catálogo

export const syncSources: SyncSource[] = [
    { id: 1, system_name: 'Valery', system_version: null, database_engine: 'Firebird', label: 'Valery / Firebird', enabled: true, syncs_count: 3 },
    { id: 2, system_name: 'Profit', system_version: '2K12', database_engine: 'SQL Server', label: 'Profit 2K12 / SQL Server', enabled: true, syncs_count: 3 },
];

export const catalog: SyncCatalogItem[] = [
    { name: 'Clientes Valery', code: 'clientes_valery', source_id: 1, source: 'Valery / Firebird', min_version: '2.0.0', enabled: true, key: 'co_cli', desc: 'Maestro de clientes desde Valery.', interval_seconds: 900 },
    { name: 'Productos Valery', code: 'productos_valery', source_id: 1, source: 'Valery / Firebird', min_version: '2.0.0', enabled: true, key: 'co_art', desc: 'Catálogo de productos e inventario desde Valery.', interval_seconds: 1800 },
    { name: 'Ventas Valery', code: 'ventas_valery', source_id: 1, source: 'Valery / Firebird', min_version: '2.2.0', enabled: true, key: 'fact_num', desc: 'Facturación y notas de entrega desde Valery.', interval_seconds: 1200 },
    { name: 'Clientes Profit', code: 'clientes_profit', source_id: 2, source: 'Profit 2K12 / SQL Server', min_version: '2.4.0', enabled: true, key: 'co_cli', desc: 'Maestro de clientes desde Profit Plus.', interval_seconds: 900 },
    { name: 'Productos Profit', code: 'productos_profit', source_id: 2, source: 'Profit 2K12 / SQL Server', min_version: '2.4.0', enabled: true, key: 'co_art', desc: 'Artículos y stock desde Profit Plus.', interval_seconds: 1800 },
    { name: 'Ventas Profit', code: 'ventas_profit', source_id: 2, source: 'Profit 2K12 / SQL Server', min_version: '2.4.1', enabled: false, key: 'fact_num', desc: 'Facturación desde Profit.', interval_seconds: 600 },
];

// ------------------------------------------------------------------ clientes y agentes

interface ClientSeed { name: string; system: 'Valery' | 'Profit'; agents: number }

const CLIENT_SEEDS: ClientSeed[] = [
    { name: 'Distribuidora El Sol', system: 'Valery', agents: 1 },
    { name: 'Supermercado Central', system: 'Profit', agents: 2 },
    { name: 'Farmacia Vida', system: 'Profit', agents: 1 },
    { name: 'Comercial Andes', system: 'Valery', agents: 1 },
    { name: 'Textiles Guayana', system: 'Valery', agents: 1 },
    { name: 'Panadería La Espiga', system: 'Valery', agents: 1 },
    { name: 'Ferretería El Tornillo', system: 'Valery', agents: 2 },
    { name: 'Licorería La Botella', system: 'Profit', agents: 1 },
    { name: 'Autopartes Miranda', system: 'Profit', agents: 2 },
    { name: 'Calzados Libertador', system: 'Valery', agents: 1 },
    { name: 'Distribuidora Oriente', system: 'Valery', agents: 3 },
    { name: 'Abastos La Economía', system: 'Valery', agents: 1 },
    { name: 'Óptica Visión Clara', system: 'Profit', agents: 1 },
    { name: 'Repuestos El Motor', system: 'Profit', agents: 2 },
    { name: 'Papelería Central', system: 'Valery', agents: 1 },
    { name: 'Charcutería Los Alpes', system: 'Valery', agents: 1 },
    { name: 'Droguería Nacional', system: 'Profit', agents: 3 },
    { name: 'Mueblería El Roble', system: 'Valery', agents: 1 },
    { name: 'Agropecuaria El Llano', system: 'Valery', agents: 2 },
    { name: 'Inversiones Costa Azul', system: 'Profit', agents: 1 },
    { name: 'Comercializadora Zulia', system: 'Profit', agents: 2 },
    { name: 'Distribuidora La Montaña', system: 'Valery', agents: 1 },
    { name: 'Cauchos Carabobo', system: 'Profit', agents: 1 },
    { name: 'Víveres Mi Pueblo', system: 'Valery', agents: 1 },
    { name: 'Electrodomésticos Total', system: 'Profit', agents: 1 },
    { name: 'Farmacia San Rafael', system: 'Profit', agents: 1 },
    { name: 'Bodegón El Faro', system: 'Valery', agents: 1 },
    { name: 'Quincalla La Popular', system: 'Valery', agents: 1 },
    { name: 'Materiales El Constructor', system: 'Profit', agents: 2 },
    { name: 'Perfumería Esencia', system: 'Valery', agents: 1 },
];

const VERSIONS = ['2.4.1', '2.4.1', '2.4.1', '2.4.0', '2.3.2', '2.2.0'];
const MACHINE_PREFIX = ['SRV', 'PC', 'CAJA', 'ADMIN'];

export interface AgentRecord extends AgentListItem {
    client_id: number;
    config: AgentDetail['config'];
    outbox: AgentDetail['outbox'];
    syncs: AgentDetail['syncs'];
    timeline: AgentDetail['timeline'];
}

export const clients: (ClientListItem & { _seed: ClientSeed })[] = [];
export const agents: AgentRecord[] = [];

let agentSeq = 101;
CLIENT_SEEDS.forEach((cs, i) => {
    const clientId = i + 1;
    for (let a = 0; a < cs.agents; a++) {
        const code = `AGT-000${agentSeq++}`;
        // Distribución: ~34 online, ~8 offline (como la maqueta), pocos enrolled/disabled.
        const roll = rnd();
        const status: AgentStatus = roll < 0.76 ? 'online' : roll < 0.94 ? 'offline' : roll < 0.98 ? 'enrolled' : 'disabled';
        const heartbeatAgo = status === 'online' ? int(3, 55) * 1000
            : status === 'offline' ? int(35, 300) * 60_000
            : status === 'enrolled' ? int(1, 3) * 86_400_000
            : int(10, 60) * 86_400_000;

        // syncs asignados según sistema del cliente
        const pool = catalog.filter((c) => c.source.startsWith(cs.system));
        const nSyncs = Math.min(pool.length, int(1, 3));
        const assigned = pool.slice(0, nSyncs).map((c) => {
            const source = syncSources.find((item) => item.id === c.source_id);

            return {
                code: c.code,
                name: c.name,
                source: {
                    database_engine: source?.database_engine ?? 'Base de datos no definida',
                    system_name: source?.system_name ?? 'Sistema administrativo no definido',
                    system_version: source?.system_version ?? 'Versión no definida',
                },
                interval_seconds: c.interval_seconds,
                status: (rnd() < 0.82 ? 'enabled' : rnd() < 0.6 ? 'paused' : 'disabled') as SyncStatus,
            };
        });

        agents.push({
            code,
            client: cs.name,
            client_id: clientId,
            machine: `${pick(MACHINE_PREFIX)}-${cs.system.toUpperCase()}-0${a + 1}`,
            version: pick(VERSIONS),
            status,
            last_heartbeat: status === 'disabled' ? null : iso(heartbeatAgo),
            ip: `190.202.${int(10, 250)}.${int(2, 250)}`,
            syncs_count: assigned.length,
            last_error: null,
            config: {
                interval_seconds: 900,
                batch_size: 500,
                endpoint: 'https://api.bapps.io/v1/ingest',
                tls: '1.3',
                log_level: 'info',
            },
            outbox: {
                pending: status === 'offline' ? int(1, 40) : 0,
                sent: int(300, 5000),
                last_sent: iso(heartbeatAgo + int(1, 20) * 1000),
            },
            syncs: assigned,
            timeline: [],
        });
    }
});

// Agente estrella de la maqueta: forzar sus datos exactos.
const star = agents[0];
star.code = 'AGT-000142';
star.client = 'Distribuidora El Sol';
star.machine = 'SRV-VALERY-01';
star.version = '2.4.1';
star.status = 'online';
star.last_heartbeat = iso(12_000);
star.ip = '190.202.14.55';

// ------------------------------------------------------------------ runs

const ERROR_CODES = ['SOURCE_CONNECTION_FAILED', 'SCHEMA_CHANGED', 'TARGET_CONNECTION_FAILED', 'INVALID_CONFIG'];
const TECH_MSGS: Record<string, string> = {
    SOURCE_CONNECTION_FAILED: 'FbException: unable to complete network request to host "localhost". Firebird no responde en el puerto 3050.',
    SCHEMA_CHANGED: 'KeyError: columna "co_seg" no existe en la tabla origen FACTURA. El esquema cambió respecto al mapeo del sincronizador.',
    TARGET_CONNECTION_FAILED: "MySQLdb.OperationalError: (2003, \"Can't connect to MySQL server on 'localhost:3306'\").",
    INVALID_CONFIG: 'ValueError: interval_seconds debe ser >= 60, se recibió 15.',
};

export interface RunRecord extends RunDetail {
    agent_code: string;
    client_id: number;
}

export const runs: RunRecord[] = [];
// El histórico generado usa 8200+; los runs exactos de la maqueta ocupan 8835–8842.
let runSeq = 8200;

function makeTimeline(status: RunStatus, trigger: TriggerType, startedAgoMs: number, durMs: number, error: string | null): RunDetail['timeline'] {
    const t: RunDetail['timeline'] = [
        { event: 'run_started', detail: `Trigger: ${trigger}`, at: iso(startedAgoMs) },
    ];
    if (status === 'running') {
        t.push({ event: 'batch_sent', detail: 'Lote 1/3 en proceso', at: iso(startedAgoMs - 2000) });
    } else if (status === 'failed') {
        t.push({ event: 'batch_sent', detail: 'Lote 1/1 iniciado', at: iso(startedAgoMs - Math.floor(durMs / 3)) });
        t.push({ event: 'sync_error', detail: `${error}`, at: iso(startedAgoMs - durMs) });
    } else if (status === 'skipped') {
        t.push({ event: 'run_skipped', detail: `${error}`, at: iso(startedAgoMs - durMs) });
    } else if (status === 'interrupted') {
        t.push({ event: 'stop_requested', detail: 'stop_run recibido', at: iso(startedAgoMs - Math.floor(durMs / 2)) });
        t.push({ event: 'run_interrupted', detail: 'Detenida en punto seguro', at: iso(startedAgoMs - durMs) });
    } else {
        t.push({ event: 'batch_sent', detail: 'Lote 1/1 completado', at: iso(startedAgoMs - Math.floor(durMs / 2)) });
        t.push({ event: 'run_finished', detail: 'Resultado: success', at: iso(startedAgoMs - durMs) });
    }
    return t;
}

function addRun(opts: {
    agent: AgentRecord;
    sync: string;
    status: RunStatus;
    trigger: TriggerType;
    startedAgoMs: number;
    durMs: number;
    error?: string | null;
    id?: string;
}): RunRecord {
    const { agent, sync, status, trigger, startedAgoMs, durMs } = opts;
    const error = opts.error ?? null;
    const ok = status === 'success';
    const read = ok ? int(200, 2500) : status === 'failed' && error === 'SCHEMA_CHANGED' ? int(100, 600) : 0;
    const run: RunRecord = {
        id: opts.id ?? `RUN-${runSeq++}`,
        client: agent.client,
        client_id: agent.client_id,
        agent: agent.code,
        agent_code: agent.code,
        sync,
        status,
        trigger,
        started_at: iso(startedAgoMs),
        ended_at: status === 'running' || status === 'stopping' ? null : iso(startedAgoMs - durMs),
        rows_read: read,
        rows_inserted: ok ? Math.floor(read * 0.04) : 0,
        rows_updated: ok ? Math.floor(read * 0.015) : 0,
        rows_failed: error === 'SCHEMA_CHANGED' ? read : 0,
        error,
        reviewed_at: null,
        reviewed_by: null,
        correlation_id: `corr-${(opts.id ?? `run-${runSeq - 1}`).toLowerCase()}`,
        tech_message: error ? TECH_MSGS[error] ?? null : null,
        timeline: makeTimeline(status, trigger, startedAgoMs, durMs, error),
    };
    runs.push(run);
    return run;
}

// Historial de ~26 h para todos los agentes online/offline.
for (const agent of agents) {
    if (agent.status === 'enrolled' || agent.status === 'disabled') continue;
    for (const s of agent.syncs) {
        if (s.status !== 'enabled') continue;
        const n = int(2, 5);
        for (let i = 0; i < n; i++) {
            const startedAgo = int(5, 26 * 60) * 60_000;
            const roll = rnd();
            const status: RunStatus = roll < 0.86 ? 'success' : roll < 0.94 ? 'failed' : 'skipped';
            const error = status === 'failed' ? pick(ERROR_CODES) : status === 'skipped' ? 'SYNC_ALREADY_RUNNING' : null;
            addRun({
                agent, sync: s.code, status,
                trigger: rnd() < 0.85 ? 'schedule' : rnd() < 0.5 ? 'manual' : 'command',
                startedAgoMs: startedAgo,
                durMs: status === 'skipped' ? 200 : int(1500, 45000),
                error,
            });
        }
    }
}

// Ejecuciones exactas de la maqueta (las más recientes).
const byCode = (c: string) => agents.find((a) => a.code === c) ?? agents[0];
const byClient = (n: string) => agents.find((a) => a.client === n) ?? agents[0];
addRun({ agent: byClient('Distribuidora El Sol'), sync: 'productos_valery', status: 'success', trigger: 'schedule', startedAgoMs: 17 * 60_000, durMs: 7000, id: 'RUN-8835' });
addRun({ agent: byClient('Supermercado Central'), sync: 'clientes_profit', status: 'success', trigger: 'schedule', startedAgoMs: 14 * 60_000, durMs: 11000, id: 'RUN-8836' });
addRun({ agent: byClient('Textiles Guayana'), sync: 'ventas_valery', status: 'failed', trigger: 'schedule', startedAgoMs: 12 * 60_000, durMs: 32000, error: 'SCHEMA_CHANGED', id: 'RUN-8837' });
addRun({ agent: byClient('Panadería La Espiga'), sync: 'productos_valery', status: 'skipped', trigger: 'command', startedAgoMs: 9 * 60_000, durMs: 200, error: 'SYNC_ALREADY_RUNNING', id: 'RUN-8838' });
addRun({ agent: byClient('Comercial Andes'), sync: 'clientes_valery', status: 'success', trigger: 'schedule', startedAgoMs: 7 * 60_000, durMs: 6400, id: 'RUN-8839' });
addRun({ agent: byClient('Farmacia Vida'), sync: 'ventas_profit', status: 'failed', trigger: 'schedule', startedAgoMs: 4 * 60_000, durMs: 3100, error: 'SOURCE_CONNECTION_FAILED', id: 'RUN-8840' });
addRun({ agent: byClient('Supermercado Central'), sync: 'productos_profit', status: 'running', trigger: 'manual', startedAgoMs: 21_000, durMs: 0, id: 'RUN-8841' });
addRun({ agent: byCode('AGT-000142'), sync: 'clientes_valery', status: 'success', trigger: 'schedule', startedAgoMs: 8_000, durMs: 8200, id: 'RUN-8842' });

// Los runs nuevos que cree la simulación continúan después de la maqueta.
runSeq = 8843;

// Marcar last_error de agentes con ejecuciones fallidas recientes.
for (const r of runs) {
    if (r.status === 'failed') {
        const a = agents.find((x) => x.code === r.agent_code);
        if (a && (!a.last_error || r.started_at > (a.last_heartbeat ?? ''))) a.last_error = r.error;
    }
}

// ------------------------------------------------------------------ comandos

export const commands: Command[] = [];
let cmdSeq = 3360;

const CMD_USERS = ['soporte@bapps', 'admin@bapps', 'operaciones@bapps'];
for (let i = 0; i < 18; i++) {
    const agent = pick(agents);
    const type = pick<CommandType>(['run_now', 'pause_sync', 'resume_sync', 'refresh_config']);
    const ago = int(10, 700) * 60_000;
    // Los comandos del histórico nacen terminales: solo los que envía el
    // usuario en la sesión transicionan pending→completed (via handlers).
    const status = rnd() < 0.85 ? 'completed' : rnd() < 0.5 ? 'failed' : 'expired';
    commands.push({
        id: `CMD-${cmdSeq++}`,
        type,
        agent: agent.code,
        by: pick(CMD_USERS),
        created_at: iso(ago),
        status,
        result: status === 'completed' ? 'OK' : null,
        expires_at: iso(ago - 7 * 60_000),
        sync_code: type === 'run_now' || type === 'pause_sync' || type === 'resume_sync' ? pick(agent.syncs)?.code ?? 'clientes_valery' : null,
    });
}

export function nextCommandId(): string {
    return `CMD-${cmdSeq++}`;
}
export function nextRunId(): string {
    return `RUN-${runSeq++}`;
}

// ------------------------------------------------------------------ auditoría

export const audit: AuditEvent[] = [];
let audSeq = 99050;

for (const c of commands) {
    audit.push({
        id: `AUD-${audSeq++}`,
        kind: 'command',
        action: `${c.type} ${c.status === 'pending' ? 'enviado' : 'ejecutado'}`,
        actor: c.by,
        target: c.agent,
        ctx: c.sync_code ?? '—',
        result: c.status,
        at: c.created_at,
    });
}
for (const r of runs) {
    if (r.status === 'failed') {
        audit.push({
            id: `AUD-${audSeq++}`,
            kind: 'error',
            action: 'sync_error',
            actor: 'sistema',
            target: r.agent,
            ctx: r.sync,
            result: r.error ?? '—',
            at: r.started_at,
        });
    } else if (r.status === 'success' && rnd() < 0.3) {
        audit.push({
            id: `AUD-${audSeq++}`,
            kind: 'event',
            action: 'run_finished',
            actor: 'sistema',
            target: r.agent,
            ctx: r.sync,
            result: 'success',
            at: r.ended_at ?? r.started_at,
        });
    }
}
for (let i = 0; i < 6; i++) {
    const agent = pick(agents);
    const isConfig = rnd() < 0.5;
    audit.push({
        id: `AUD-${audSeq++}`,
        kind: isConfig ? 'config' : 'auth',
        action: isConfig ? 'Intervalo modificado' : 'Login administrativo',
        actor: pick(CMD_USERS),
        target: isConfig ? agent.code : pick(CMD_USERS),
        ctx: isConfig ? (pick(agent.syncs)?.code ?? '—') : '—',
        result: 'ok',
        at: iso(int(10, 1200) * 60_000),
    });
}

export function pushAudit(e: Omit<AuditEvent, 'id'>): void {
    audit.push({ ...e, id: `AUD-${audSeq++}` });
}

// ------------------------------------------------------------------ clientes (derivados)

CLIENT_SEEDS.forEach((cs, i) => {
    const clientId = i + 1;
    const myAgents = agents.filter((a) => a.client_id === clientId);
    const myRuns = runs.filter((r) => r.client_id === clientId);
    const openErrors = myRuns.filter((r) => r.status === 'failed').length;
    const anyOffline = myAgents.some((a) => a.status === 'offline');
    const allEnrolled = myAgents.every((a) => a.status === 'enrolled');
    const lastSync = myRuns.map((r) => r.ended_at ?? r.started_at).sort().at(-1) ?? null;
    clients.push({
        id: clientId,
        name: cs.name,
        system: cs.system,
        agents: myAgents.length,
        syncs: myAgents.reduce((n, a) => n + a.syncs_count, 0),
        health: allEnrolled ? 'enrolled' : openErrors > 1 ? 'error' : anyOffline || openErrors === 1 ? 'warning' : 'ok',
        health_reason: null,
        last_sync: lastSync,
        open_errors: openErrors,
        _seed: cs,
    });
});
