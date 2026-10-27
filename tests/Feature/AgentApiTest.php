<?php

namespace Tests\Feature;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncCommand;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Hash;
use Tests\TestCase;

class AgentApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_agent_can_enroll_and_receives_a_rotated_credential(): void
    {
        $agent = $this->agent('enrollment-secret');

        $response = $this->postJson('/api/v1/agent/enroll', [
            'agent_code' => $agent->agent_code,
            'enrollment_token' => 'enrollment-secret',
            'machine_name' => 'SERVER-VALERY',
            'agent_version' => '1.0.0',
            'os' => 'Windows Server',
        ]);

        $response->assertCreated()
            ->assertJsonPath('agent_code', $agent->agent_code)
            ->assertJsonStructure(['agent_token', 'config_version']);

        $this->assertFalse(Hash::check('enrollment-secret', $agent->fresh()->credential_hash));
    }

    public function test_agent_receives_only_its_versioned_configuration(): void
    {
        $agent = $this->agent('agent-token');
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '1.0.0', 'default_interval_seconds' => 900,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'enabled', 'interval_seconds' => 900, 'config_json' => ['batch_size' => 200],
        ]);

        $this->agentRequest($agent, 'agent-token')
            ->getJson('/api/v1/agent/config')
            ->assertOk()
            ->assertJsonPath('agent_code', $agent->agent_code)
            ->assertJsonPath('syncs.0.code', 'clientes_valery')
            ->assertJsonPath('syncs.0.config.batch_size', 200);
    }

    public function test_p2_agent_receives_its_mysql_target_in_schema_1_1(): void
    {
        $agent = $this->agent('agent-token');
        $agent->update([
            'version' => '0.2.0',
            'config_version' => 2,
            'bapps_mysql_config' => [
                'host' => 'mysql.bapps.test', 'port' => 3306, 'database' => 'bapps',
                'username' => 'sync', 'password' => 'secret',
            ],
            'bapps_mysql_configured_at' => now(),
        ]);

        $this->agentRequest($agent, 'agent-token')
            ->getJson('/api/v1/agent/config')
            ->assertOk()
            ->assertJsonPath('schema_version', '1.1')
            ->assertJsonPath('version', 2)
            ->assertJsonPath('targets.bapps_mysql.host', 'mysql.bapps.test')
            ->assertJsonPath('targets.bapps_mysql.password', 'secret');
    }

    public function test_agent_can_send_a_heartbeat_without_active_runs(): void
    {
        $agent = $this->agent('agent-token');

        $this->agentRequest($agent, 'agent-token')
            ->postJson('/api/v1/agent/heartbeat', [
                'schema_version' => '1.0',
                'agent_code' => $agent->agent_code,
                'agent_version' => '1.0.0',
                'config_version' => 1,
                'machine_name' => 'SERVER-VALERY',
                'status' => 'online',
                'running_runs' => [],
                'outbox' => ['pending_count' => 0, 'pending_bytes' => 0],
            ])
            ->assertOk()
            ->assertJsonPath('acknowledged', true);

        $this->assertDatabaseHas('agents', ['id' => $agent->id, 'status' => 'online']);
    }

    public function test_agent_api_rejects_an_oversized_payload_before_processing_it(): void
    {
        $agent = $this->agent('agent-token');

        $this->agentRequest($agent, 'agent-token')
            ->postJson('/api/v1/agent/events', [
                'schema_version' => '1.0',
                'event_id' => 'EVT-TOO-LARGE',
                'event_type' => 'outbox_warning',
                'agent_code' => $agent->agent_code,
                'occurred_at' => now()->toISOString(),
                'payload' => ['message' => str_repeat('x', 70_000)],
            ])
            ->assertStatus(413)
            ->assertJsonPath('error.code', 'PAYLOAD_TOO_LARGE');

        $this->assertDatabaseMissing('sync_events', ['event_id' => 'EVT-TOO-LARGE']);
    }

    public function test_command_claim_is_scoped_and_idempotent_for_known_ids(): void
    {
        $agent = $this->agent('agent-token');
        $other = $this->agent('other-token', 'AGT-OTHER');

        SyncCommand::query()->create([
            'command_id' => 'CMD-MINE', 'agent_id' => $agent->id, 'command_type' => 'run_now',
            'sync_code' => 'clientes_valery', 'status' => 'pending', 'idempotency_key' => 'idem-mine',
            'issued_at' => now(), 'expires_at' => now()->addMinutes(10),
        ]);
        SyncCommand::query()->create([
            'command_id' => 'CMD-OTHER', 'agent_id' => $other->id, 'command_type' => 'run_now',
            'sync_code' => 'clientes_valery', 'status' => 'pending', 'idempotency_key' => 'idem-other',
            'issued_at' => now(), 'expires_at' => now()->addMinutes(10),
        ]);

        $this->agentRequest($agent, 'agent-token')
            ->postJson('/api/v1/agent/commands/claim', [
                'agent_code' => $agent->agent_code, 'max_commands' => 5,
            ])
            ->assertOk()
            ->assertJsonPath('data.0.command_id', 'CMD-MINE')
            ->assertJsonCount(1, 'data');

        $this->assertDatabaseHas('sync_commands', ['command_id' => 'CMD-MINE', 'status' => 'claimed']);
    }

    public function test_expired_command_lease_is_reclaimed_when_the_command_is_still_valid(): void
    {
        $agent = $this->agent('agent-token');
        SyncCommand::query()->create([
            'command_id' => 'CMD-RECLAIM', 'agent_id' => $agent->id, 'command_type' => 'refresh_config',
            'status' => 'claimed', 'idempotency_key' => 'idem-reclaim', 'issued_at' => now()->subMinute(),
            'expires_at' => now()->addMinutes(10), 'claimed_at' => now()->subMinute(),
            'lease_expires_at' => now()->subSecond(),
        ]);

        $this->agentRequest($agent, 'agent-token')
            ->postJson('/api/v1/agent/commands/claim', [
                'agent_code' => $agent->agent_code, 'max_commands' => 5,
            ])
            ->assertOk()
            ->assertJsonPath('data.0.command_id', 'CMD-RECLAIM')
            ->assertJsonCount(1, 'data');

        $this->assertDatabaseHas('sync_commands', ['command_id' => 'CMD-RECLAIM', 'status' => 'claimed']);
    }

    public function test_expired_command_is_never_delivered_to_the_agent(): void
    {
        $agent = $this->agent('agent-token');
        SyncCommand::query()->create([
            'command_id' => 'CMD-EXPIRED', 'agent_id' => $agent->id, 'command_type' => 'run_now',
            'sync_code' => 'clientes_valery', 'status' => 'pending', 'idempotency_key' => 'idem-expired',
            'issued_at' => now()->subMinutes(31), 'expires_at' => now()->subMinute(),
        ]);

        $this->agentRequest($agent, 'agent-token')
            ->postJson('/api/v1/agent/commands/claim', [
                'agent_code' => $agent->agent_code, 'max_commands' => 5,
            ])
            ->assertOk()
            ->assertJsonCount(0, 'data');

        $this->assertDatabaseHas('sync_commands', ['command_id' => 'CMD-EXPIRED', 'status' => 'expired']);
    }

    public function test_command_result_is_idempotent_and_keeps_its_first_terminal_result(): void
    {
        $agent = $this->agent('agent-token');
        SyncCommand::query()->create([
            'command_id' => 'CMD-RESULT', 'agent_id' => $agent->id, 'command_type' => 'run_now',
            'sync_code' => 'clientes_valery', 'status' => 'claimed', 'idempotency_key' => 'idem-result',
            'issued_at' => now(), 'expires_at' => now()->addMinutes(10),
        ]);
        $first = [
            'status' => 'completed', 'completed_at' => now()->toISOString(), 'result' => ['run_id' => 'RUN-RESULT'],
        ];

        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/commands/CMD-RESULT/result', $first)
            ->assertOk()
            ->assertJsonPath('status', 'completed')
            ->assertJsonPath('result.run_id', 'RUN-RESULT');

        $duplicate = [
            'status' => 'failed', 'completed_at' => now()->addSecond()->toISOString(), 'result' => ['error_code' => 'IGNORED'],
        ];
        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/commands/CMD-RESULT/result', $duplicate)
            ->assertOk()
            ->assertJsonPath('status', 'completed')
            ->assertJsonPath('result.run_id', 'RUN-RESULT');

        $this->assertDatabaseHas('sync_commands', [
            'command_id' => 'CMD-RESULT', 'status' => 'completed', 'result_json' => json_encode(['run_id' => 'RUN-RESULT']),
        ]);
    }

    public function test_an_agent_cannot_complete_another_agents_command(): void
    {
        $owner = $this->agent('owner-token');
        $other = $this->agent('other-token', 'AGT-OTHER');
        SyncCommand::query()->create([
            'command_id' => 'CMD-OWNER-ONLY', 'agent_id' => $owner->id, 'command_type' => 'refresh_config',
            'status' => 'claimed', 'idempotency_key' => 'idem-owner-only',
            'issued_at' => now(), 'expires_at' => now()->addMinutes(10),
        ]);

        $this->agentRequest($other, 'other-token')
            ->postJson('/api/v1/agent/commands/CMD-OWNER-ONLY/result', [
                'status' => 'completed', 'completed_at' => now()->toISOString(), 'result' => [],
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('command_id');

        $this->assertDatabaseHas('sync_commands', ['command_id' => 'CMD-OWNER-ONLY', 'status' => 'claimed']);
    }

    public function test_event_ingestion_is_idempotent_and_does_not_cross_agents(): void
    {
        $agent = $this->agent('agent-token');
        $otherAgent = $this->agent('other-token', 'AGT-OTHER');
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '1.0.0', 'default_interval_seconds' => 900,
        ]);

        $payload = [
            'schema_version' => '1.0', 'event_id' => 'EVT-0001', 'event_type' => 'run_finished',
            'agent_code' => $agent->agent_code, 'run_id' => 'RUN-0001', 'correlation_id' => 'CORR-0001',
            'sync_code' => $catalog->code, 'occurred_at' => now()->toISOString(),
            'payload' => ['status' => 'success', 'trigger' => 'command', 'duration_ms' => 1200, 'rows_read' => 12],
        ];

        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/events', $payload)
            ->assertOk()->assertJsonPath('duplicate', false);
        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/events', $payload)
            ->assertOk()->assertJsonPath('duplicate', true);

        $crossAgentPayload = [...$payload, 'event_id' => 'EVT-0002', 'agent_code' => $otherAgent->agent_code];
        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/events', $crossAgentPayload)
            ->assertForbidden()
            ->assertJsonPath('error.code', 'AUTHENTICATION_FAILED');

        $this->assertDatabaseCount('sync_events', 1);
        $this->assertDatabaseHas('sync_runs', ['run_id' => 'RUN-0001', 'status' => 'success']);
    }

    public function test_a_late_run_started_event_does_not_revert_a_terminal_run(): void
    {
        $agent = $this->agent('agent-token');
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'min_agent_version' => '1.0.0', 'default_interval_seconds' => 900,
        ]);
        $finishedAt = now();
        $finished = [
            'schema_version' => '1.0', 'event_id' => 'EVT-FINISHED', 'event_type' => 'run_finished',
            'agent_code' => $agent->agent_code, 'run_id' => 'RUN-OUT-OF-ORDER', 'correlation_id' => 'CORR-ORDER',
            'sync_code' => $catalog->code, 'occurred_at' => $finishedAt->toISOString(),
            'payload' => [
                'status' => 'success', 'trigger' => 'command', 'duration_ms' => 1200,
                'rows_read' => 12, 'rows_inserted' => 3, 'rows_updated' => 9,
            ],
        ];

        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/events', $finished)
            ->assertOk()->assertJsonPath('duplicate', false);

        $lateStart = [
            ...$finished,
            'event_id' => 'EVT-LATE-START',
            'event_type' => 'run_started',
            'occurred_at' => $finishedAt->subSecond()->toISOString(),
            'payload' => ['trigger' => 'command'],
        ];
        $this->agentRequest($agent, 'agent-token')->postJson('/api/v1/agent/events', $lateStart)
            ->assertOk()->assertJsonPath('duplicate', false);

        $this->assertDatabaseCount('sync_events', 2);
        $this->assertDatabaseHas('sync_runs', [
            'run_id' => 'RUN-OUT-OF-ORDER', 'status' => 'success',
            'rows_read' => 12, 'rows_inserted' => 3, 'rows_updated' => 9,
        ]);
    }

    private function agent(string $token, string $code = 'AGT-000142'): Agent
    {
        $client = Client::query()->create(['name' => "Cliente {$code}", 'system_type' => 'BAPPS']);

        return Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => $code, 'credential_hash' => Hash::make($token),
        ]);
    }

    private function agentRequest(Agent $agent, string $token): static
    {
        return $this->withHeader('X-Agent-Code', $agent->agent_code)
            ->withToken($token);
    }
}
