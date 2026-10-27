<?php

namespace App\Actions\ControlApi;

use App\Models\AgentSync;
use App\Models\SyncCommand;
use App\Models\SyncRun;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;

final class RetryFailedRun
{
    private const MIN_AGENT_VERSION = '0.5.2';

    public function __construct(private readonly RecordControlAudit $recordAudit) {}

    public function handle(string $runId, ?int $actorId): SyncRun
    {
        return DB::transaction(function () use ($runId, $actorId): SyncRun {
            $failedRun = SyncRun::query()
                ->with(['agent', 'catalog'])
                ->where('run_id', $runId)
                ->lockForUpdate()
                ->first();

            if ($failedRun === null) {
                throw new RuntimeException("La ejecución {$runId} no existe.");
            }
            if ($failedRun->status !== 'failed') {
                throw new RuntimeException('Solo se pueden reintentar ejecuciones fallidas.');
            }

            $agent = $failedRun->agent;
            $catalog = $failedRun->catalog;
            if ($agent === null || $catalog === null || ! $agent->enabled) {
                throw new RuntimeException('La ejecución ya no tiene un agente y sincronizador habilitados.');
            }
            if (! $catalog->enabled_globally) {
                throw new RuntimeException("El sincronizador {$catalog->code} está deshabilitado globalmente.");
            }
            if (version_compare((string) ($agent->version ?? '0.0.0'), self::MIN_AGENT_VERSION, '<')) {
                throw new RuntimeException('El agente requiere versión '.self::MIN_AGENT_VERSION.' o superior para reintentar con seguridad.');
            }

            $assignment = AgentSync::query()
                ->where('agent_id', $agent->id)
                ->where('sync_catalog_id', $catalog->id)
                ->where('status', 'enabled')
                ->exists();
            if (! $assignment) {
                throw new RuntimeException("El sincronizador {$catalog->code} no está habilitado para {$agent->agent_code}.");
            }

            $retry = SyncRun::query()->create([
                'run_id' => 'RUN-'.Str::lower((string) Str::uuid()),
                'agent_id' => $agent->id,
                'client_id' => $agent->client_id,
                'sync_catalog_id' => $catalog->id,
                'status' => 'pending',
                'trigger' => 'manual',
                'started_at' => now(),
            ]);

            $command = SyncCommand::query()->create([
                'command_id' => 'CMD-'.Str::upper((string) Str::uuid()),
                'agent_id' => $agent->id,
                'command_type' => 'run_now',
                'sync_code' => $catalog->code,
                'run_id' => $retry->run_id,
                'payload_json' => ['sync_code' => $catalog->code, 'run_id' => $retry->run_id],
                'status' => 'pending',
                'idempotency_key' => 'retry-'.$failedRun->id.'-'.Str::uuid(),
                'created_by' => $actorId,
                'issued_at' => now(),
                'expires_at' => now()->addMinutes(30),
            ]);

            $retry->update(['command_id' => $command->command_id]);

            $this->recordAudit->handle('command', 'retry_run', $actorId, 'run', $retry->run_id, [
                'sync_code' => $catalog->code,
                'source_run_id' => $failedRun->run_id,
                'command_id' => $command->command_id,
            ]);

            return $retry->fresh(['agent.client', 'catalog']);
        });
    }
}
