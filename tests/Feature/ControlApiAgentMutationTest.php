<?php

namespace Tests\Feature;

use App\Http\Middleware\AuthenticateControlApi;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncCommand;
use App\Models\SyncRecipe;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ControlApiAgentMutationTest extends TestCase
{
    use RefreshDatabase;

    public function test_operator_can_queue_a_run_now_for_an_assigned_sync(): void
    {
        [$agent] = $this->agentWithSync();

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
                'type' => 'run_now', 'sync_code' => 'clientes_valery',
            ])
            ->assertCreated()
            ->assertJsonPath('type', 'run_now')
            ->assertJsonPath('agent', $agent->agent_code)
            ->assertJsonPath('sync_code', 'clientes_valery')
            ->assertJsonPath('status', 'pending');

        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'command', 'action' => 'run_now', 'target_type' => 'command',
        ]);
    }

    public function test_operator_can_version_an_agent_sync_configuration(): void
    {
        [$agent, $assignment] = $this->agentWithSync();

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->patchJson("/api/v1/agents/{$agent->agent_code}/syncs/clientes_valery", [
                'status' => 'paused', 'interval_seconds' => 1200,
            ])
            ->assertOk()
            ->assertJsonPath('syncs.0.status', 'paused')
            ->assertJsonPath('syncs.0.interval_seconds', 1200);

        $this->assertSame(2, $agent->fresh()->config_version);
        $this->assertSame(2, $assignment->fresh()->config_version);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'config', 'action' => 'update_agent_sync', 'target_type' => 'agent_sync',
        ]);
    }

    public function test_pause_and_resume_commands_update_the_visible_assignment_state(): void
    {
        [$agent, $assignment] = $this->agentWithSync();
        $api = $this->withoutMiddleware(AuthenticateControlApi::class);

        $api->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
            'type' => 'pause_sync', 'sync_code' => 'clientes_valery',
        ])->assertCreated()->assertJsonPath('type', 'pause_sync');

        $this->assertSame('paused', $assignment->fresh()->status);
        $this->assertSame(2, $agent->fresh()->config_version);

        $api->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
            'type' => 'resume_sync', 'sync_code' => 'clientes_valery',
        ])->assertCreated()->assertJsonPath('type', 'resume_sync');

        $this->assertSame('enabled', $assignment->fresh()->status);
        $this->assertSame(3, $agent->fresh()->config_version);
    }

    public function test_operator_can_assign_an_enabled_catalog_sync_to_a_compatible_agent(): void
    {
        [$agent] = $this->agentWithSync();
        $agent->update(['enabled' => true, 'version' => '0.6.4']);
        $catalog = SyncCatalog::query()->create([
            'code' => 'sellers_valery',
            'name' => 'Vendedores Valery',
            'source_type' => 'firebird',
            'min_agent_version' => '0.6.4',
            'default_interval_seconds' => 120,
            'enabled_globally' => true,
        ]);
        $recipe = SyncRecipe::query()->create(['sync_catalog_id' => $catalog->id]);
        $version = $recipe->versions()->create([
            'version' => 1,
            'payload_json' => ['recipe_code' => 'sellers_valery'],
            'payload_hash' => 'sha256:test',
            'published_at' => now(),
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/agents/{$agent->agent_code}/syncs", [
                'sync_code' => 'sellers_valery',
                'status' => 'enabled',
                'interval_seconds' => 120,
            ])
            ->assertCreated()
            ->assertJsonPath('syncs.1.code', 'sellers_valery')
            ->assertJsonPath('syncs.1.interval_seconds', 120);

        $this->assertDatabaseHas('agent_syncs', [
            'agent_id' => $agent->id,
            'sync_catalog_id' => $catalog->id,
            'sync_recipe_version_id' => $version->id,
            'status' => 'enabled',
            'interval_seconds' => 120,
        ]);
        $this->assertSame(2, $agent->fresh()->config_version);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'config', 'action' => 'assign_agent_sync', 'target_type' => 'agent_sync',
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/agents/{$agent->agent_code}/syncs", [
                'sync_code' => 'sellers_valery',
                'status' => 'enabled',
                'interval_seconds' => 120,
            ])
            ->assertConflict()
            ->assertJsonPath('error.code', 'ASSIGNMENT_REJECTED');
    }

    public function test_operator_can_request_and_read_a_safe_source_table_inspection_from_an_online_agent(): void
    {
        [$agent] = $this->agentWithSync();
        $agent->update([
            'enabled' => true,
            'status' => 'online',
            'last_seen_at' => now(),
            'version' => '0.6.3',
        ]);

        $response = $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
                'type' => 'inspect_source_table',
                'profile_ref' => 'default',
                'driver' => 'firebird',
                'table' => 'VENDEDORES',
                'position' => 3,
            ])
            ->assertCreated()
            ->assertJsonPath('type', 'inspect_source_table')
            ->assertJsonPath('status', 'pending');

        $commandId = $response->json('id');
        $command = SyncCommand::query()->where('command_id', $commandId)->firstOrFail();
        $this->assertSame([
            'profile_ref' => 'default',
            'driver' => 'firebird',
            'table' => 'VENDEDORES',
            'position' => 3,
        ], $command->payload_json);

        $command->update([
            'status' => 'completed',
            'completed_at' => now(),
            'result_json' => [
                'driver' => 'firebird',
                'profile_ref' => 'default',
                'schema' => null,
                'table' => 'VENDEDORES',
                'position' => 3,
                'has_row' => true,
                'has_next' => true,
                'columns' => [
                    ['name' => 'CODIGO', 'type' => 'str', 'sample' => 'V01'],
                    ['name' => 'NOMBRE', 'type' => 'str', 'sample' => 'María'],
                ],
            ],
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->getJson("/api/v1/agents/{$agent->agent_code}/commands/{$commandId}")
            ->assertOk()
            ->assertJsonPath('status', 'completed')
            ->assertJsonPath('result.table', 'VENDEDORES')
            ->assertJsonPath('result.position', 3)
            ->assertJsonPath('result.columns.1.name', 'NOMBRE')
            ->assertJsonMissingPath('result.password');
    }

    public function test_source_inspection_requires_an_online_agent_and_safe_identifiers(): void
    {
        [$agent] = $this->agentWithSync();
        $api = $this->withoutMiddleware(AuthenticateControlApi::class);

        $api->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
            'type' => 'inspect_source_table',
            'profile_ref' => 'default',
            'driver' => 'firebird',
            'table' => 'VENDEDORES',
            'position' => 1,
        ])->assertConflict()->assertJsonPath('error.code', 'COMMAND_REJECTED');

        $agent->update(['enabled' => true, 'status' => 'online', 'last_seen_at' => now()]);
        $api->postJson("/api/v1/agents/{$agent->agent_code}/commands", [
            'type' => 'inspect_source_table',
            'profile_ref' => 'default',
            'driver' => 'firebird',
            'table' => 'VENDEDORES;DROP',
            'position' => 1,
        ])->assertUnprocessable();
    }

    /** @return array{Agent, AgentSync} */
    private function agentWithSync(): array
    {
        $agent = Agent::query()->create([
            'client_id' => Client::query()->create(['name' => 'Cliente Control', 'system_type' => 'BAPPS'])->id,
            'agent_code' => 'AGT-CONTROL', 'credential_hash' => 'not-used', 'config_version' => 1,
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '0.3.0', 'default_interval_seconds' => 900,
        ]);
        $assignment = AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'enabled', 'interval_seconds' => 900, 'config_version' => 1,
        ]);

        return [$agent, $assignment];
    }
}
