<?php

namespace Tests\Feature;

use App\Actions\ControlApi\QueueAgentRun;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class QueueAgentRunTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_queues_a_manual_run_for_an_enabled_assignment(): void
    {
        $agent = Agent::query()->create([
            'client_id' => Client::query()->create(['name' => 'Cliente P3', 'system_type' => 'BAPPS'])->id,
            'agent_code' => 'AGT-P3', 'credential_hash' => 'not-used',
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '0.3.0', 'default_interval_seconds' => 900,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'enabled', 'interval_seconds' => 900,
        ]);

        $command = app(QueueAgentRun::class)->handle($agent, 'clientes_valery');

        $this->assertSame('run_now', $command->command_type);
        $this->assertSame('clientes_valery', $command->payload_json['sync_code']);
        $this->assertDatabaseHas('sync_commands', ['id' => $command->id, 'status' => 'pending']);
    }
}
