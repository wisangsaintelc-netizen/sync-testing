<?php

namespace App\Actions\AgentApi;

use App\Models\Agent;
use App\Models\SyncCommand;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

class CompleteCommand
{
    public function handle(Agent $agent, string $commandId, array $data): SyncCommand
    {
        return DB::transaction(function () use ($agent, $commandId, $data): SyncCommand {
            $command = SyncCommand::query()
                ->where('agent_id', $agent->id)
                ->where('command_id', $commandId)
                ->lockForUpdate()
                ->first();

            if ($command === null) {
                throw ValidationException::withMessages(['command_id' => 'El comando no pertenece al agente autenticado.']);
            }

            if (in_array($command->status, ['completed', 'failed', 'skipped'], true)) {
                return $command;
            }

            $command->update([
                'status' => $data['status'],
                'completed_at' => $data['completed_at'],
                'result_json' => $data['result'] ?? [],
            ]);

            return $command->refresh();
        });
    }
}
