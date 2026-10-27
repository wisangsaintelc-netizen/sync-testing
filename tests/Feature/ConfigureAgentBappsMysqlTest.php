<?php

namespace Tests\Feature;

use App\Http\Middleware\AuthenticateControlApi;
use App\Models\Agent;
use App\Models\Client;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ConfigureAgentBappsMysqlTest extends TestCase
{
    use RefreshDatabase;

    public function test_control_api_encrypts_and_versions_the_mysql_target(): void
    {
        $agent = Agent::query()->create([
            'client_id' => Client::query()->create(['name' => 'Cliente P2', 'system_type' => 'BAPPS'])->id,
            'agent_code' => 'AGT-P2', 'credential_hash' => 'not-used', 'config_version' => 1,
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->putJson('/api/v1/agents/AGT-P2/bapps-mysql', [
                'host' => '192.168.0.10', 'port' => 3306, 'database' => 'bapps',
                'username' => 'sync_user', 'password' => 'never-in-response',
            ])
            ->assertOk()
            ->assertJsonPath('config_version', 2)
            ->assertJsonPath('bapps_mysql.host', '192.168.0.10')
            ->assertJsonMissingPath('bapps_mysql.password');

        $fresh = $agent->fresh();
        $this->assertSame('never-in-response', $fresh->bapps_mysql_config['password']);
        $this->assertDatabaseHas('agents', ['id' => $agent->id, 'config_version' => 2]);
    }
}
