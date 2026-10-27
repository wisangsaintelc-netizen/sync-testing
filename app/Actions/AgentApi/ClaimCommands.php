<?php

namespace App\Actions\AgentApi;

use App\Models\Agent;
use App\Models\SyncCommand;
use Illuminate\Support\Carbon;
use Illuminate\Support\Facades\DB;

class ClaimCommands
{
    /** @return array<int, array<string, mixed>> */
    public function handle(Agent $agent, int $maxCommands, array $knownCommandIds): array
    {
        return DB::transaction(function () use ($agent, $maxCommands, $knownCommandIds): array {
            $now = now();

            SyncCommand::query()
                ->where('agent_id', $agent->id)
                ->whereIn('status', ['pending', 'claimed'])
                ->where('expires_at', '<=', $now)
                ->update(['status' => 'expired', 'updated_at' => $now]);

            // A worker can die after claiming. Return only still-valid expired
            // leases to pending so another agent loop can deliver the same
            // idempotent command again.
            SyncCommand::query()
                ->where('agent_id', $agent->id)
                ->where('status', 'claimed')
                ->where('expires_at', '>', $now)
                ->where('lease_expires_at', '<=', $now)
                ->update([
                    'status' => 'pending',
                    'claimed_at' => null,
                    'lease_expires_at' => null,
                    'updated_at' => $now,
                ]);

            $commands = SyncCommand::query()
                ->where('agent_id', $agent->id)
                ->where('status', 'pending')
                ->where('expires_at', '>', $now)
                ->when($knownCommandIds !== [], fn ($query) => $query->whereNotIn('command_id', $knownCommandIds))
                ->orderBy('created_at')
                ->limit($maxCommands)
                ->lockForUpdate()
                ->get();

            $leaseExpiresAt = $now->copy()->addSeconds(config('bapps-sync.command_lease_seconds'));

            foreach ($commands as $command) {
                $command->update([
                    'status' => 'claimed',
                    'claimed_at' => $now,
                    'lease_expires_at' => $leaseExpiresAt,
                ]);
            }

            return $commands->map(fn (SyncCommand $command): array => $this->toDelivery($command, $leaseExpiresAt))->all();
        });
    }

    /** @return array<string, mixed> */
    private function toDelivery(SyncCommand $command, Carbon $leaseExpiresAt): array
    {
        return [
            'schema_version' => '1.0',
            'command_id' => $command->command_id,
            'type' => $command->command_type,
            'issued_at' => $command->issued_at->toISOString(),
            'expires_at' => $command->expires_at->toISOString(),
            'lease_expires_at' => $leaseExpiresAt->toISOString(),
            'idempotency_key' => $command->idempotency_key,
            'payload' => $command->payload_json ?? array_filter([
                'sync_code' => $command->sync_code,
                'run_id' => $command->run_id,
            ]),
        ];
    }
}
