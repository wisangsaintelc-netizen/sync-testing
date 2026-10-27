<?php

namespace App\Http\Controllers\ControlApi;

use App\Http\Controllers\Controller;
use App\Http\Resources\ControlApi\AgentListResource;
use App\Http\Resources\ControlApi\AuditEventResource;
use App\Http\Resources\ControlApi\RunListResource;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\SyncAuditEvent;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;

class DashboardMetricsController extends Controller
{
    public function __invoke(): JsonResponse
    {
        $lastDay = now()->subDay();
        $recentAgents = Agent::query()->with('client')->withCount('syncs')->orderByDesc('last_seen_at')->limit(5)->get();
        $recentRuns = SyncRun::query()->with(['agent.client', 'catalog'])->latest('started_at')->limit(5)->get();
        $recentAudit = SyncAuditEvent::query()->latest('occurred_at')->limit(5)->get();
        $assigned = AgentSync::query()->with(['agent.client', 'catalog'])->latest()->limit(5)->get();

        return response()->json([
            'agents_total' => Agent::count(),
            'agents_delta_week' => Agent::where('created_at', '>=', now()->subWeek())->count(),
            'agents_online' => Agent::query()->online()->count(),
            'agents_offline' => Agent::query()->offline()->count(),
            'syncs_active' => AgentSync::where('status', 'enabled')->count(),
            'failed_runs_24h' => SyncRun::where('status', 'failed')->whereNull('reviewed_at')->where('started_at', '>=', $lastDay)->count(),
            'audit_events_24h' => SyncAuditEvent::where('occurred_at', '>=', $lastDay)->count(),
            'recent_agents' => AgentListResource::collection($recentAgents)->resolve(),
            'recent_audit' => AuditEventResource::collection($recentAudit)->resolve(),
            'recent_runs' => RunListResource::collection($recentRuns)->resolve(),
            'assigned_syncs' => $assigned->map(fn (AgentSync $sync) => [
                'code' => $sync->catalog?->code ?? '',
                'client' => $sync->agent?->client?->name ?? '',
                'interval_seconds' => $sync->interval_seconds,
                'status' => $sync->status,
            ])->values()->all(),
        ]);
    }
}
