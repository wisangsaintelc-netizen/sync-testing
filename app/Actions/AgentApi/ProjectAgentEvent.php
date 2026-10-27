<?php

namespace App\Actions\AgentApi;

use App\Models\Agent;
use App\Models\SyncCatalog;
use App\Models\SyncEvent;
use App\Models\SyncRun;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;

class ProjectAgentEvent
{
    /** @return array{duplicate: bool} */
    public function handle(Agent $agent, array $data): array
    {
        return DB::transaction(function () use ($agent, $data): array {
            if (SyncEvent::query()->where('event_id', $data['event_id'])->exists()) {
                return ['duplicate' => true];
            }

            SyncEvent::query()->create([
                'event_id' => $data['event_id'],
                'schema_version' => $data['schema_version'],
                'event_type' => $data['event_type'],
                'agent_id' => $agent->id,
                'client_id' => $agent->client_id,
                'sync_code' => $data['sync_code'] ?? null,
                'run_id' => $data['run_id'] ?? null,
                'correlation_id' => $data['correlation_id'] ?? null,
                'occurred_at' => $data['occurred_at'],
                'received_at' => now(),
                'payload_json' => $data['payload'],
            ]);

            $this->projectRun($agent, $data);

            return ['duplicate' => false];
        });
    }

    private function projectRun(Agent $agent, array $data): void
    {
        if (! in_array($data['event_type'], ['run_started', 'run_finished'], true)
            || empty($data['run_id'])
            || empty($data['sync_code'])) {
            return;
        }

        $catalog = SyncCatalog::query()->where('code', $data['sync_code'])->first();

        // El evento bruto ya quedó durable. No se fabrica una relación inválida
        // si una configuración atrasada reporta un sync que el centro no conoce.
        if ($catalog === null) {
            return;
        }

        $payload = $data['payload'];
        $status = Arr::get($payload, 'status', $data['event_type'] === 'run_started' ? 'running' : 'failed');
        $terminal = ['success', 'failed', 'interrupted', 'skipped'];
        $run = SyncRun::query()->where('run_id', $data['run_id'])->lockForUpdate()->first();

        if ($run !== null && in_array($run->status, $terminal, true) && $data['event_type'] === 'run_started') {
            return;
        }

        $attributes = [
            'agent_id' => $agent->id,
            'client_id' => $agent->client_id,
            'sync_catalog_id' => $catalog->id,
            'correlation_id' => $data['correlation_id'] ?? null,
            'status' => $status,
            'trigger' => Arr::get($payload, 'trigger'),
            'started_at' => $data['event_type'] === 'run_started' ? $data['occurred_at'] : ($run?->started_at ?? $data['occurred_at']),
            'agent_version' => $agent->version,
        ];

        if ($data['event_type'] === 'run_finished') {
            $attributes = array_merge($attributes, [
                'finished_at' => $data['occurred_at'],
                'duration_ms' => Arr::get($payload, 'duration_ms'),
                'rows_read' => Arr::get($payload, 'rows_read', 0),
                'rows_inserted' => Arr::get($payload, 'rows_inserted', 0),
                'rows_updated' => Arr::get($payload, 'rows_updated', 0),
                'rows_deleted' => Arr::get($payload, 'rows_deleted', 0),
                'rows_failed' => Arr::get($payload, 'rows_failed', 0),
                'error_code' => Arr::get($payload, 'error_code'),
                'error_message' => Arr::get($payload, 'error_message'),
            ]);
        }

        if ($run === null) {
            SyncRun::query()->create(['run_id' => $data['run_id'], ...$attributes]);

            return;
        }

        $run->update($attributes);
    }
}
