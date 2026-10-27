<?php

namespace Tests\Feature;

use App\Http\Controllers\AgentApi\AgentConfigController;
use App\Http\Middleware\AuthenticateControlApi;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncRecipeVersion;
use App\Models\SyncRun;
use App\Models\SyncSource;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ControlApiCatalogMutationTest extends TestCase
{
    use RefreshDatabase;

    public function test_operator_can_create_a_catalog_entry_with_its_functional_key(): void
    {
        $source = SyncSource::query()->create([
            'system_name' => 'Profit', 'system_version' => '2K12', 'database_engine' => 'SQL Server',
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson('/api/v1/syncs', [
                'name' => 'Ventas Profit', 'code' => 'ventas_profit',
                'source_id' => $source->id, 'min_version' => '2.4.0',
                'key' => 'fact_num', 'desc' => 'Facturación de Profit.', 'interval_seconds' => 900,
            ])
            ->assertCreated()
            ->assertJsonPath('code', 'ventas_profit')
            ->assertJsonPath('key', 'fact_num')
            ->assertJsonPath('enabled', true);

        $this->assertDatabaseHas('sync_catalog', [
            'code' => 'ventas_profit', 'sync_source_id' => $source->id, 'functional_key' => 'fact_num', 'enabled_globally' => 1,
        ]);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'config', 'action' => 'create_catalog', 'target_type' => 'sync_catalog', 'target_id' => 'ventas_profit',
        ]);
    }

    public function test_catalog_code_is_normalized_to_lowercase(): void
    {
        $source = SyncSource::query()->create([
            'system_name' => 'Valery', 'database_engine' => 'Firebird',
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson('/api/v1/syncs', [
                'name' => 'Productos terminados', 'code' => 'PRODUCTOS_TERMINADOS',
                'source_id' => $source->id, 'min_version' => '0.6.8',
                'key' => 'CODIGO_PRODUCTO', 'interval_seconds' => 900,
            ])
            ->assertCreated()
            ->assertJsonPath('code', 'productos_terminados');
    }

    public function test_operator_can_create_a_catalog_and_publish_its_initial_read_recipe_atomically(): void
    {
        $source = SyncSource::query()->create([
            'system_name' => 'Valery', 'system_version' => '3', 'database_engine' => 'Firebird',
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson('/api/v1/syncs', [
                'name' => 'Clientes declarativo',
                'code' => 'clientes_valery_v2',
                'source_id' => $source->id,
                'min_version' => '0.6.2',
                'key' => 'CO_CLI',
                'desc' => 'Fotografía completa de clientes.',
                'interval_seconds' => 900,
                'recipe' => $this->readRecipe('clientes_valery_v2'),
            ])
            ->assertCreated()
            ->assertJsonPath('code', 'clientes_valery_v2');

        $catalog = SyncCatalog::query()->where('code', 'clientes_valery_v2')->firstOrFail();
        $version = SyncRecipeVersion::query()
            ->whereHas('recipe', fn ($recipe) => $recipe->where('sync_catalog_id', $catalog->id))
            ->firstOrFail();

        $this->assertSame(1, $version->version);
        $this->assertSame('declarative_table_reader', $version->payload_json['engine']);
        $this->assertSame(['CO_CLI', 'CLI_DES', 'RIF'], $version->payload_json['source']['columns']);
        $this->assertDatabaseHas('sync_audit_events', [
            'action' => 'publish_recipe', 'target_type' => 'sync_recipe_version', 'target_id' => (string) $version->id,
        ]);
    }

    public function test_catalog_is_not_created_when_recipe_driver_does_not_match_its_source(): void
    {
        $source = SyncSource::query()->create([
            'system_name' => 'Valery', 'database_engine' => 'Firebird',
        ]);
        $recipe = $this->readRecipe('clientes_invalido');
        $recipe['source']['driver'] = 'sqlserver';
        $recipe['source']['schema'] = 'dbo';

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson('/api/v1/syncs', [
                'name' => 'Clientes inválido',
                'code' => 'clientes_invalido',
                'source_id' => $source->id,
                'min_version' => '0.6.2',
                'key' => 'CO_CLI',
                'interval_seconds' => 900,
                'recipe' => $recipe,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('recipe.source.driver');

        $this->assertDatabaseMissing('sync_catalog', ['code' => 'clientes_invalido']);
    }

    public function test_operator_can_manage_sources_for_catalogs(): void
    {
        $api = $this->withoutMiddleware(AuthenticateControlApi::class);
        $source = $api->postJson('/api/v1/sync-sources', [
            'system_name' => 'Profit', 'system_version' => '2K8', 'database_engine' => 'SQL Server',
        ])
            ->assertCreated()
            ->assertJsonPath('label', 'Profit 2K8 / SQL Server')
            ->json();

        $api->patchJson("/api/v1/sync-sources/{$source['id']}", ['enabled' => false])
            ->assertOk()
            ->assertJsonPath('enabled', false);

        $api->getJson('/api/v1/sync-sources')
            ->assertOk()
            ->assertJsonPath('total', 1);
    }

    public function test_disabled_source_cannot_be_assigned_to_a_new_catalog(): void
    {
        $source = SyncSource::query()->create([
            'database_engine' => 'Firebird',
            'enabled' => false,
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->postJson('/api/v1/syncs', [
                'name' => 'Sync bloqueado',
                'code' => 'sync_bloqueado',
                'source_id' => $source->id,
                'min_version' => '1.0.0',
                'key' => 'sync_key',
                'interval_seconds' => 60,
            ])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('source_id');
    }

    public function test_operator_can_delete_only_an_unused_source(): void
    {
        $used = SyncSource::query()->create(['system_name' => 'Sistema', 'database_engine' => 'Motor']);
        $unused = SyncSource::query()->create(['system_name' => 'Temporal', 'database_engine' => 'Motor']);
        SyncCatalog::query()->create([
            'code' => 'sync_usado', 'functional_key' => 'key_used', 'sync_source_id' => $used->id,
            'name' => 'Sync usado', 'source_type' => $used->label, 'min_agent_version' => '1.0.0',
            'default_interval_seconds' => 60,
        ]);

        $api = $this->withoutMiddleware(AuthenticateControlApi::class);
        $api->deleteJson("/api/v1/sync-sources/{$used->id}")
            ->assertConflict()
            ->assertJsonPath('error.code', 'SOURCE_IN_USE');
        $api->deleteJson("/api/v1/sync-sources/{$unused->id}")
            ->assertNoContent();

        $this->assertDatabaseHas('sync_sources', ['id' => $used->id]);
        $this->assertDatabaseMissing('sync_sources', ['id' => $unused->id]);
    }

    public function test_operator_can_disable_a_catalog_without_losing_assignment_state(): void
    {
        $client = Client::query()->create(['name' => 'Cliente Catálogo', 'system_type' => 'Valery']);
        $agent = Agent::query()->create([
            'client_id' => $client->id, 'agent_code' => 'AGT-CATALOG', 'status' => 'online',
            'credential_hash' => 'not-used', 'config_version' => 3,
        ]);
        $catalog = SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'functional_key' => 'co_cli', 'name' => 'Clientes Valery',
            'source_type' => 'Valery / Firebird', 'min_agent_version' => '0.3.0',
            'enabled_globally' => true, 'default_interval_seconds' => 60,
        ]);
        AgentSync::query()->create([
            'agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id,
            'status' => 'paused', 'interval_seconds' => 60,
        ]);
        $run = SyncRun::query()->create([
            'run_id' => 'RUN-CATALOG-RETIRED', 'agent_id' => $agent->id, 'client_id' => $client->id,
            'sync_catalog_id' => $catalog->id, 'status' => 'success',
        ]);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->patchJson('/api/v1/syncs/clientes_valery', ['enabled' => false, 'interval_seconds' => 120])
            ->assertOk()
            ->assertJsonPath('enabled', false)
            ->assertJsonPath('interval_seconds', 120);

        $this->assertDatabaseHas('agent_syncs', ['agent_id' => $agent->id, 'status' => 'paused']);
        $this->assertDatabaseHas('sync_catalog', ['id' => $catalog->id, 'enabled_globally' => 0, 'default_interval_seconds' => 120]);
        $this->assertSame(4, $agent->fresh()->config_version);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'config', 'action' => 'update_catalog', 'target_type' => 'sync_catalog', 'target_id' => 'clientes_valery',
        ]);

        request()->attributes->set('agent', $agent->fresh());
        $config = app(AgentConfigController::class)()->getData(true);
        $this->assertSame('disabled', $config['syncs'][0]['status']);

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->getJson('/api/v1/agents/AGT-CATALOG')
            ->assertOk()
            ->assertJsonPath('syncs.0.status', 'disabled');

        $this->withoutMiddleware(AuthenticateControlApi::class)
            ->deleteJson('/api/v1/syncs/clientes_valery')
            ->assertNoContent();

        $this->assertSoftDeleted('sync_catalog', ['id' => $catalog->id]);
        $this->assertDatabaseMissing('agent_syncs', ['agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id]);
        $this->assertDatabaseHas('sync_runs', ['id' => $run->id, 'sync_catalog_id' => $catalog->id]);
        $this->assertSame('clientes_valery', $run->fresh()->catalog?->code);
        $this->assertSame(5, $agent->fresh()->config_version);
        $this->assertDatabaseHas('sync_audit_events', [
            'kind' => 'config', 'action' => 'delete_catalog', 'target_type' => 'sync_catalog', 'target_id' => 'clientes_valery',
        ]);
    }

    public function test_catalog_code_cannot_be_changed_and_filters_by_global_state(): void
    {
        SyncCatalog::query()->create([
            'code' => 'clientes_valery', 'functional_key' => 'co_cli', 'name' => 'Clientes Valery',
            'source_type' => 'Valery / Firebird', 'min_agent_version' => '0.3.0',
            'enabled_globally' => false, 'default_interval_seconds' => 60,
        ]);

        $api = $this->withoutMiddleware(AuthenticateControlApi::class);
        $api->patchJson('/api/v1/syncs/clientes_valery', ['code' => 'otro_codigo'])
            ->assertUnprocessable()
            ->assertJsonValidationErrors('code');
        $api->getJson('/api/v1/syncs?status=disabled')
            ->assertOk()
            ->assertJsonPath('total', 1);
    }

    private function readRecipe(string $code): array
    {
        return [
            'schema_version' => '1.0',
            'recipe_code' => $code,
            'engine' => 'declarative_table_reader',
            'minimum_agent_version' => '0.6.2',
            'source' => [
                'profile_ref' => 'default',
                'driver' => 'firebird',
                'table' => 'CLIENTES',
                'columns' => ['CO_CLI', 'CLI_DES', 'RIF'],
            ],
            'target' => [
                'profile_ref' => 'bapps_mysql',
                'table' => 'CLIENTES',
                'strategy' => 'full_snapshot',
                'ownership' => 'create_new',
            ],
            'limits' => [
                'batch_rows' => 1000,
                'statement_timeout_seconds' => 60,
                'max_runtime_seconds' => 3600,
            ],
        ];
    }
}
