<?php

namespace Tests\Feature;

use App\Http\Middleware\AuthenticateControlApi;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncRun;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Str;
use Tests\TestCase;

class RetryFailedRunTest extends TestCase
{
    use RefreshDatabase;

    public function test_a_failed_run_creates_a_new_pending_run_and_preassigned_command(): void
    {
        $failedRun = $this->failedRun();

        $response = $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/runs/{$failedRun->run_id}/retry")
            ->assertOk()
            ->assertJsonPath('status', 'pending')
            ->assertJsonPath('trigger', 'manual');

        $retryId = $response->json('id');
        $this->assertNotSame($failedRun->run_id, $retryId);
        $this->assertDatabaseHas('sync_runs', ['run_id' => $retryId, 'status' => 'pending']);
        $this->assertDatabaseHas('sync_commands', [
            'run_id' => $retryId, 'command_type' => 'run_now', 'status' => 'pending',
        ]);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'command', 'action' => 'retry_run', 'target_type' => 'run', 'target_id' => $retryId,
        ]);
    }

    public function test_retry_rejects_non_failed_runs_and_agents_without_the_protocol_version(): void
    {
        $success = $this->failedRun(['status' => 'success']);
        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/runs/{$success->run_id}/retry")
            ->assertStatus(409)
            ->assertJsonPath('error.code', 'RETRY_REJECTED');

        $oldAgentRun = $this->failedRun(['agent_version' => '0.4.7']);
        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson("/api/v1/runs/{$oldAgentRun->run_id}/retry")
            ->assertStatus(409)
            ->assertJsonPath('error.code', 'RETRY_REJECTED');
    }

    private function failedRun(array $runOverrides = []): SyncRun
    {
        $client = Client::query()->create(['name' => 'Cliente Retry '.Str::random(4), 'system_type' => 'Valery']);
        $agent = Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => 'AGT-RETRY-'.Str::upper(Str::random(4)),
            'version' => $runOverrides['agent_version'] ?? '0.5.2', 'credential_hash' => 'not-used',
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_'.Str::lower(Str::random(6)), 'functional_key' => 'co_cli',
            'name' => 'Clientes', 'source_type' => 'firebird', 'min_agent_version' => '0.5.2',
            'default_interval_seconds' => 60,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id, 'status' => 'enabled', 'interval_seconds' => 60,
        ]);

        return SyncRun::query()->create([
            'run_id' => 'RUN-FAILED-'.Str::lower(Str::random(8)), 'agent_id' => $agent->id,
            'client_id' => $client->id, 'sync_catalog_id' => $catalog->id,
            'status' => $runOverrides['status'] ?? 'failed', 'trigger' => 'command',
            'started_at' => now()->subMinute(), 'finished_at' => now(), 'error_code' => 'SOURCE_CONNECTION_FAILED',
        ]);
    }
}
