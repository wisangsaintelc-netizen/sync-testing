<?php

namespace Tests\Feature;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncCommand;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class DemoProvisionCommandTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_provisions_a_reusable_demo_environment_and_optional_command(): void
    {
        $this->artisan('bapps:demo-provision', [
            '--agent-code' => 'AGT-DEMO-TEST',
            '--enrollment-token' => 'demo-enrollment-token-test',
            '--with-command' => true,
        ])->assertSuccessful();

        $operator = User::query()->where('email', 'operator@bapps.test')->firstOrFail();
        $client = Client::query()->where('name', 'Cliente de demostración BAPPS')->firstOrFail();
        $agent = Agent::query()->where('agent_code', 'AGT-DEMO-TEST')->firstOrFail();
        $catalog = SyncCatalog::query()->where('code', 'clientes_valery')->firstOrFail();

        $this->assertTrue(Hash::check('demo-enrollment-token-test', $agent->credential_hash));
        $this->assertDatabaseHas('agent_syncs', [
            'agent_id' => $agent->id,
            'sync_catalog_id' => $catalog->id,
            'status' => 'enabled',
        ]);
        $this->assertDatabaseHas('sync_commands', [
            'command_id' => 'CMD-DEMO-RUN-NOW',
            'agent_id' => $agent->id,
            'created_by' => $operator->id,
            'status' => 'pending',
        ]);

        $this->assertSame($client->id, $agent->client_id);
        $this->assertSame(1, AgentSync::query()->count());
        $this->assertSame(1, SyncCommand::query()->count());
    }

    public function test_it_can_generate_a_portable_bootstrap_file(): void
    {
        $bootstrap = storage_path('framework/testing/bootstrap.json');

        $this->artisan('bapps:demo-provision', [
            '--agent-code' => 'AGT-BOOTSTRAP',
            '--enrollment-token' => 'bootstrap-enrollment-token-test',
            '--bootstrap-output' => $bootstrap,
            '--base-url' => 'http://192.168.1.50:8000',
        ])->assertSuccessful();

        $data = json_decode((string) file_get_contents($bootstrap), true, 512, JSON_THROW_ON_ERROR);

        $this->assertSame('1.0', $data['schema_version']);
        $this->assertSame('AGT-BOOTSTRAP', $data['agent_code']);
        $this->assertSame('http://192.168.1.50:8000', $data['base_url']);
        $this->assertSame('bootstrap-enrollment-token-test', $data['enrollment_token']);
    }
}
