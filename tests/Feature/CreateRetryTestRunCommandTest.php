<?php

namespace Tests\Feature;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class CreateRetryTestRunCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_creates_a_synthetic_failed_run_for_an_enabled_assignment(): void
    {
        $agent = Agent::query()->create([
            'client_id' => Client::query()->create(['name' => 'Cliente Retry Test', 'system_type' => 'BAPPS'])->id,
            'agent_code' => 'AGT-RETRY-TEST', 'version' => '0.5.2', 'credential_hash' => 'not-used',
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '0.5.2', 'default_interval_seconds' => 900,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'enabled', 'interval_seconds' => 900,
        ]);

        $this->artisan('bapps:create-retry-test-run', ['agent-code' => $agent->agent_code])
            ->assertSuccessful();

        $this->assertDatabaseHas('sync_runs', [
            'agent_id' => $agent->id,
            'status' => 'failed',
            'error_code' => 'TARGET_CONNECTION_FAILED',
        ]);
    }
}
