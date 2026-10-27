<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\SyncCommand;
use App\Models\SyncRun;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;

final class QueueAgentCommand
{
    public function __construct(
        private readonly UpdateAgentSync $updateAgentSync,
        private readonly RecordControlAudit $recordAudit,
    ) {}

    public function handle(Agent $agent, array $data, ?int $actorId): SyncCommand
    {
        if (! $agent->enabled) {
            throw new RuntimeException('El agente está deshabilitado.');
        }

        $type = $data['type'];
        $syncCode = $data['sync_code'] ?? null;
        $runId = $data['run_id'] ?? null;
        $payload = array_filter([
            'sync_code' => $syncCode,
            'run_id' => $runId,
            'profile_ref' => $data['profile_ref'] ?? null,
            'driver' => $data['driver'] ?? null,
            'schema' => $data['schema'] ?? null,
            'table' => $data['table'] ?? null,
            'position' => $data['position'] ?? null,
        ], static fn (mixed $value): bool => $value !== null && $value !== '');

        if (in_array($type, ['run_now', 'pause_sync', 'resume_sync'], true)) {
            $assigned = $agent->syncs()
                ->whereHas('catalog', fn ($query) => $query->where('code', $syncCode))
                ->exists();
            if (! $assigned) {
                throw new RuntimeException("El sincronizador {$syncCode} no está asignado a {$agent->agent_code}.");
            }
        }

        if ($type === 'stop_run' && ! SyncRun::query()->where('agent_id', $agent->id)->where('run_id', $runId)->exists()) {
            throw new RuntimeException("La ejecución {$runId} no pertenece a {$agent->agent_code}.");
        }

        if ($type === 'inspect_source_table' && $agent->visibleStatus() !== 'online') {
            throw new RuntimeException("El agente {$agent->agent_code} debe estar online para inspeccionar la fuente.");
        }

        return DB::transaction(function () use ($agent, $actorId, $payload, $runId, $syncCode, $type): SyncCommand {
            if ($type === 'pause_sync') {
                $this->updateAgentSync->handle($agent, $syncCode, ['status' => 'paused'], $actorId);
            }
            if ($type === 'resume_sync') {
                $this->updateAgentSync->handle($agent, $syncCode, ['status' => 'enabled'], $actorId);
            }

            $command = SyncCommand::query()->create([
                'command_id' => 'CMD-'.Str::upper((string) Str::uuid()),
                'agent_id' => $agent->id,
                'command_type' => $type,
                'sync_code' => $syncCode,
                'run_id' => $runId,
                'payload_json' => $payload,
                'status' => 'pending',
                'idempotency_key' => 'control-'.$agent->id.'-'.$type.'-'.Str::uuid(),
                'created_by' => $actorId,
                'issued_at' => now(),
                'expires_at' => $type === 'inspect_source_table' ? now()->addMinutes(5) : now()->addMinutes(30),
            ]);

            $this->recordAudit->handle('command', $type, $actorId, 'command', $command->command_id, array_filter([
                'agent_code' => $agent->agent_code,
                'sync_code' => $syncCode,
                'run_id' => $runId,
                'profile_ref' => $payload['profile_ref'] ?? null,
                'driver' => $payload['driver'] ?? null,
                'schema' => $payload['schema'] ?? null,
                'table' => $payload['table'] ?? null,
                'position' => $payload['position'] ?? null,
            ]));

            return $command;
        });
    }
}
