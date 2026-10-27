<?php

namespace App\Http\Resources\ControlApi;

use App\Models\Agent;
use App\Models\SyncRun;
use Illuminate\Http\Request;

/** @mixin Agent */
class AgentDetailResource extends AgentListResource
{
    public function toArray(Request $request): array
    {
        $syncs = $this->syncs;
        $runs = SyncRun::query()
            ->where('agent_id', $this->getKey())
            ->with(['agent.client', 'catalog'])
            ->latest('started_at')
            ->limit(20)
            ->get();
        $commands = $this->commands->sortByDesc('issued_at')->take(20)->values();
        $timeline = collect($runs)
            ->map(fn (SyncRun $run) => [
                'type' => $run->status === 'failed' ? 'sync_error' : 'run_finished',
                'detail' => ($run->catalog?->code ?? 'sync').' · '.$run->status,
                'at' => ($run->finished_at ?? $run->started_at)?->toISOString(),
            ]);

        if ($this->last_seen_at) {
            $timeline->push([
                'type' => 'heartbeat',
                'detail' => 'v'.($this->version ?? '—'),
                'at' => $this->last_seen_at->toISOString(),
            ]);
        }

        $firstSync = $syncs->first();
        $config = $firstSync?->config_json ?? [];

        return [
            ...parent::toArray($request),
            'config' => [
                'interval_seconds' => $firstSync?->interval_seconds ?? 900,
                'batch_size' => $config['batch_size'] ?? 500,
                'endpoint' => $config['endpoint'] ?? config('app.url'),
                'tls' => $config['tls'] ?? 'default',
                'log_level' => $config['log_level'] ?? 'info',
            ],
            'outbox' => ['pending' => 0, 'sent' => 0, 'last_sent' => null],
            'syncs' => $syncs->map(fn ($sync) => [
                'code' => $sync->catalog?->code ?? '',
                'name' => $sync->catalog?->name ?? '',
                'source' => [
                    'database_engine' => $sync->catalog?->source?->database_engine ?? $sync->catalog?->source_type ?? 'Base de datos no definida',
                    'system_name' => $sync->catalog?->source?->system_name ?? 'Sistema administrativo no definido',
                    'system_version' => $sync->catalog?->source?->system_version ?? 'Versión no definida',
                ],
                'interval_seconds' => $sync->interval_seconds,
                // The catalog is the global safety switch. Keep the assignment state
                // intact in storage, but never present a globally disabled sync as runnable.
                'status' => $sync->catalog?->enabled_globally ? $sync->status : 'disabled',
            ])->values()->all(),
            'commands' => CommandResource::collection($commands)->resolve(),
            'runs' => RunListResource::collection($runs)->resolve(),
            'timeline' => $timeline->filter(fn (array $item) => $item['at'] !== null)->sortByDesc('at')->take(50)->values()->all(),
        ];
    }
}
