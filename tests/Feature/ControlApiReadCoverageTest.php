<?php

namespace Tests\Feature;

use App\Http\Middleware\AuthenticateControlApi;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncAuditEvent;
use App\Models\SyncCatalog;
use App\Models\SyncRun;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ControlApiReadCoverageTest extends TestCase
{
    use RefreshDatabase;

    public function test_clients_return_operational_health_and_detail(): void
    {
        [$client, $agent, $catalog] = $this->clientWithAgent();
        SyncRun::query()->create([
            'run_id' => 'RUN-CLIENT', 'agent_id' => $agent->id, 'client_id' => $client->id,
            'sync_catalog_id' => $catalog->id, 'status' => 'success', 'trigger' => 'command',
            'started_at' => now()->subSecond(), 'finished_at' => now(),
        ]);

        $api = $this->withoutMiddleware(AuthenticateControlApi::class);
        $api->getJson('/api/v1/clients')
            ->assertOk()
            ->assertJsonPath('data.0.name', 'Cliente Lecturas')
            ->assertJsonPath('data.0.health', 'ok')
            ->assertJsonPath('data.0.syncs', 1);
        $api->getJson("/api/v1/clients/{$client->id}")
            ->assertOk()
            ->assertJsonPath('agents_list.0.code', 'AGT-READ')
            ->assertJsonPath('runs.0.id', 'RUN-CLIENT');
    }

    public function test_audit_and_catalog_queries_use_real_models(): void
    {
        [, , $catalog] = $this->clientWithAgent();
        SyncAuditEvent::query()->create([
            'kind' => 'command', 'action' => 'run_now', 'actor_type' => 'user',
            'target_type' => 'agent', 'target_id' => 'AGT-READ', 'result' => 'completed',
            'context_json' => ['sync_code' => 'clientes_valery'], 'occurred_at' => now(),
        ]);

        $api = $this->withoutMiddleware(AuthenticateControlApi::class);
        $api->getJson('/api/v1/audit?kind=command')
            ->assertOk()
            ->assertJsonPath('data.0.action', 'run_now')
            ->assertJsonPath('data.0.ctx', 'clientes_valery');
        $api->getJson('/api/v1/syncs?search=clientes')
            ->assertOk()
            ->assertJsonPath('data.0.code', $catalog->code)
            ->assertJsonPath('data.0.source', 'firebird');
    }

    /** @return array{Client, Agent, SyncCatalog} */
    private function clientWithAgent(): array
    {
        $client = Client::query()->create(['name' => 'Cliente Lecturas', 'system_type' => 'Valery']);
        $agent = Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => 'AGT-READ', 'status' => 'online',
            'last_seen_at' => now(), 'credential_hash' => 'not-used',
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '0.3.0', 'default_interval_seconds' => 60,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'enabled', 'interval_seconds' => 60,
        ]);

        return [$client, $agent, $catalog];
    }
}
