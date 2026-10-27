<?php

namespace Tests\Feature;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncAuditEvent;
use App\Models\SyncCatalog;
use App\Models\SyncRun;
use App\Models\SyncSource;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ControlApiReadTest extends TestCase
{
    use RefreshDatabase;

    public function test_login_issues_a_revocable_expiring_bearer_token_and_rejects_bad_credentials(): void
    {
        $user = User::factory()->create(['email' => 'operator@bapps.test', 'password' => 'secret-password']);

        $this->postJson('/api/v1/auth/login', ['email' => $user->email, 'password' => 'wrong-password'])
            ->assertUnauthorized()
            ->assertJsonPath('error.code', 'AUTHENTICATION_FAILED');

        $token = $this->postJson('/api/v1/auth/login', ['email' => $user->email, 'password' => 'secret-password'])
            ->assertOk()
            ->assertJsonStructure(['token', 'user' => ['name', 'email', 'role']])
            ->assertJsonPath('user.email', $user->email)
            ->assertJsonPath('user.role', 'operator')
            ->json('token');

        $this->assertDatabaseHas('personal_access_tokens', [
            'tokenable_type' => User::class,
            'tokenable_id' => $user->id,
            'name' => 'control-api',
        ]);
        $this->assertDatabaseMissing('personal_access_tokens', ['token' => $token]);
    }

    public function test_a_revoked_control_token_cannot_access_the_api(): void
    {
        $token = $this->token();
        $user = User::query()->firstOrFail();
        $user->tokens()->where('name', 'control-api')->delete();

        $this->withToken($token)->getJson('/api/v1/agents')
            ->assertUnauthorized()
            ->assertJsonPath('error.code', 'UNAUTHENTICATED');
    }

    public function test_read_endpoints_require_a_bearer_token(): void
    {
        $this->getJson('/api/v1/agents')
            ->assertUnauthorized()
            ->assertJsonPath('error.code', 'UNAUTHENTICATED');
    }

    public function test_agent_status_and_metrics_expire_after_the_heartbeat_timeout(): void
    {
        $token = $this->token();
        $client = Client::query()->create(['name' => 'Cliente Heartbeat', 'system_type' => 'BAPPS']);
        $fresh = Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => 'AGT-FRESH', 'status' => 'online',
            'last_seen_at' => now()->subSecond(), 'credential_hash' => 'fresh-token',
        ]);
        $stale = Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => 'AGT-STALE', 'status' => 'online',
            'last_seen_at' => now()->subSeconds(121), 'credential_hash' => 'stale-token',
        ]);

        $this->withToken($token)->getJson('/api/v1/agents?status=online')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.code', $fresh->agent_code)
            ->assertJsonPath('data.0.status', 'online');
        $this->withToken($token)->getJson('/api/v1/agents?status=offline')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.code', $stale->agent_code)
            ->assertJsonPath('data.0.status', 'offline');
        $this->withToken($token)->getJson('/api/v1/dashboard/metrics')
            ->assertOk()
            ->assertJsonPath('agents_online', 1)
            ->assertJsonPath('agents_offline', 1);
        $this->withToken($token)->getJson('/api/v1/clients')
            ->assertOk()
            ->assertJsonPath('data.0.health', 'warning')
            ->assertJsonPath('data.0.health_reason', 'Agente sin conexión: AGT-STALE.');
    }

    public function test_agents_dashboard_and_runs_match_the_public_contract(): void
    {
        $token = $this->token();
        [$agent, $catalog] = $this->agentWithSync();
        $run = SyncRun::query()->create([
            'run_id' => 'RUN-100',
            'agent_id' => $agent->id,
            'client_id' => $agent->client_id,
            'sync_catalog_id' => $catalog->id,
            'correlation_id' => 'CORR-100',
            'status' => 'failed',
            'trigger' => 'command',
            'started_at' => now()->subMinute(),
            'finished_at' => now(),
            'rows_read' => 25,
            'rows_inserted' => 4,
            'rows_updated' => 2,
            'rows_failed' => 1,
            'error_code' => 'SOURCE_CONNECTION_FAILED',
            'error_message' => 'The source database is unavailable.',
        ]);
        SyncAuditEvent::query()->create([
            'kind' => 'error', 'action' => 'sync_error', 'actor_type' => 'agent',
            'target_type' => 'agent', 'target_id' => $agent->agent_code,
            'result' => 'SOURCE_CONNECTION_FAILED', 'context_json' => ['run_id' => $run->run_id], 'occurred_at' => now(),
        ]);

        $this->withToken($token)->getJson('/api/v1/agents?page=1&page_size=25')
            ->assertOk()
            ->assertJsonPath('page', 1)
            ->assertJsonPath('page_size', 25)
            ->assertJsonPath('total', 1)
            ->assertJsonPath('data.0.code', $agent->agent_code)
            ->assertJsonPath('data.0.client', 'Valery')
            ->assertJsonPath('data.0.last_error', 'SOURCE_CONNECTION_FAILED');

        $this->withToken($token)->getJson("/api/v1/agents/{$agent->agent_code}")
            ->assertOk()
            ->assertJsonPath('code', $agent->agent_code)
            ->assertJsonPath('syncs.0.code', $catalog->code)
            ->assertJsonPath('syncs.0.source.database_engine', 'Firebird')
            ->assertJsonPath('syncs.0.source.system_name', 'Valery')
            ->assertJsonPath('syncs.0.source.system_version', '3.0')
            ->assertJsonPath('runs.0.id', $run->run_id)
            ->assertJsonMissingPath('data');

        $this->withToken($token)->getJson("/api/v1/clients/{$agent->client_id}")
            ->assertOk()
            ->assertJsonPath('open_errors', 1)
            ->assertJsonPath('errors.0.id', $run->run_id)
            ->assertJsonPath('errors.0.error', 'SOURCE_CONNECTION_FAILED');

        $this->withToken($token)->getJson('/api/v1/dashboard/metrics')
            ->assertOk()
            ->assertJsonPath('agents_total', 1)
            ->assertJsonPath('agents_online', 1)
            ->assertJsonPath('failed_runs_24h', 1)
            ->assertJsonPath('recent_runs.0.id', $run->run_id);

        $this->withToken($token)->getJson("/api/v1/runs/{$run->run_id}")
            ->assertOk()
            ->assertJsonPath('id', $run->run_id)
            ->assertJsonPath('correlation_id', 'CORR-100')
            ->assertJsonPath('tech_message', 'The source database is unavailable.');
    }

    public function test_unknown_agent_and_run_return_the_documented_not_found_shape(): void
    {
        $token = $this->token();

        $this->withToken($token)->getJson('/api/v1/agents/AGT-UNKNOWN')
            ->assertNotFound()
            ->assertJsonPath('error.code', 'NOT_FOUND');
        $this->withToken($token)->getJson('/api/v1/runs/RUN-UNKNOWN')
            ->assertNotFound()
            ->assertJsonPath('error.code', 'NOT_FOUND');
    }

    public function test_reviewing_a_failed_run_clears_its_pending_alert_without_changing_history(): void
    {
        $token = $this->token();
        $user = User::query()->firstOrFail();
        [$agent, $catalog] = $this->agentWithSync();
        $run = SyncRun::query()->create([
            'run_id' => 'RUN-REVIEW-100',
            'agent_id' => $agent->id,
            'client_id' => $agent->client_id,
            'sync_catalog_id' => $catalog->id,
            'status' => 'failed',
            'trigger' => 'manual',
            'started_at' => now()->subMinute(),
            'finished_at' => now(),
            'error_code' => 'TARGET_CONNECTION_FAILED',
        ]);

        $this->withToken($token)->postJson("/api/v1/runs/{$run->run_id}/review")
            ->assertOk()
            ->assertJsonPath('id', $run->run_id)
            ->assertJsonStructure(['reviewed_at', 'reviewed_by']);

        $this->assertDatabaseHas('sync_runs', [
            'run_id' => $run->run_id,
            'status' => 'failed',
            'reviewed_by' => $user->id,
        ]);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'error',
            'action' => 'review_run',
            'target_type' => 'run',
            'target_id' => $run->run_id,
        ]);

        $this->withToken($token)->getJson("/api/v1/clients/{$agent->client_id}")
            ->assertOk()
            ->assertJsonPath('health', 'ok')
            ->assertJsonPath('open_errors', 0)
            ->assertJsonCount(0, 'errors');
    }

    /** @return array{Agent, SyncCatalog} */
    private function agentWithSync(): array
    {
        $client = Client::query()->create(['name' => 'Valery', 'system_type' => 'BAPPS']);
        $agent = Agent::query()->create([
            'client_id' => $client->id,
            'agent_code' => 'AGT-VALERY',
            'machine_name' => 'SRV-VALERY',
            'version' => '1.0.0',
            'status' => 'online',
            'last_seen_at' => now(),
            'last_ip' => '127.0.0.1',
            'credential_hash' => 'not-used-by-control-api',
        ]);
        $source = SyncSource::query()->create([
            'database_engine' => 'Firebird',
            'system_name' => 'Valery',
            'system_version' => '3.0',
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'name' => 'Clientes Valery', 'source_type' => 'firebird',
            'sync_source_id' => $source->id,
            'min_agent_version' => '1.0.0', 'default_interval_seconds' => 900,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id, 'status' => 'enabled', 'interval_seconds' => 900,
        ]);

        return [$agent, $catalog];
    }

    private function token(): string
    {
        $user = User::factory()->create(['password' => 'secret-password']);

        return $this->postJson('/api/v1/auth/login', ['email' => $user->email, 'password' => 'secret-password'])
            ->json('token');
    }
}
