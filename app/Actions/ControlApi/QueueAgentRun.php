<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\SyncCommand;
use Illuminate\Support\Str;
use RuntimeException;

final class QueueAgentRun
{
    public function handle(Agent $agent, string $syncCode): SyncCommand
    {
        $assignment = $agent->syncs()
            ->where('status', 'enabled')
            ->whereHas('catalog', fn ($query) => $query->where('code', $syncCode))
            ->first();

        if ($assignment === null) {
            throw new RuntimeException("El agente {$agent->agent_code} no tiene habilitado {$syncCode}.");
        }

        return SyncCommand::query()->create([
            'command_id' => 'CMD-'.Str::upper((string) Str::uuid()),
            'agent_id' => $agent->id,
            'command_type' => 'run_now',
            'sync_code' => $syncCode,
            'payload_json' => ['sync_code' => $syncCode],
            'status' => 'pending',
            'idempotency_key' => 'run-now-'.$agent->id.'-'.$syncCode.'-'.Str::uuid(),
            'issued_at' => now(),
            'expires_at' => now()->addMinutes(30),
        ]);
    }
}
