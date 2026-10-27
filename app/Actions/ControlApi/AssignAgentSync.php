<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\SyncCatalog;
use App\Models\SyncRecipeVersion;
use Illuminate\Support\Facades\DB;
use RuntimeException;

final class AssignAgentSync
{
    public function __construct(private readonly RecordControlAudit $recordAudit) {}

    public function handle(Agent $agent, array $data, ?int $actorId = null): AgentSync
    {
        return DB::transaction(function () use ($agent, $data, $actorId): AgentSync {
            $catalog = SyncCatalog::query()
                ->where('code', $data['sync_code'])
                ->lockForUpdate()
                ->first();

            if ($catalog === null) {
                throw new RuntimeException("El sincronizador {$data['sync_code']} no existe.");
            }
            if (! $catalog->enabled_globally) {
                throw new RuntimeException("El sincronizador {$catalog->code} está deshabilitado en el catálogo.");
            }
            if (! $agent->enabled) {
                throw new RuntimeException("El agente {$agent->agent_code} está deshabilitado.");
            }
            if (version_compare((string) ($agent->version ?? '0.0.0'), $catalog->min_agent_version, '<')) {
                throw new RuntimeException(
                    "{$catalog->code} requiere agente {$catalog->min_agent_version} o posterior."
                );
            }
            if (AgentSync::query()->where('agent_id', $agent->id)->where('sync_catalog_id', $catalog->id)->exists()) {
                throw new RuntimeException("El sincronizador {$catalog->code} ya está asignado a {$agent->agent_code}.");
            }
            if ($catalog->direction === 'write') {
                if (empty($data['config']) || empty($data['secrets']['orders_api_token'])) {
                    throw new RuntimeException('El escritor requiere configuración local y token de la API de pedidos.');
                }
                $alreadyWriting = AgentSync::query()
                    ->where('agent_id', $agent->id)
                    ->where('config_json->profile_ref', $data['config']['profile_ref'])
                    ->whereHas('catalog', fn ($query) => $query->where('direction', 'write'))
                    ->exists();
                if ($alreadyWriting) {
                    throw new RuntimeException('Este agente ya tiene un escritor asignado para ese perfil Firebird.');
                }
            }

            $recipeVersionId = SyncRecipeVersion::query()
                ->whereHas('recipe', fn ($recipe) => $recipe->where('sync_catalog_id', $catalog->id))
                ->orderByDesc('version')
                ->value('id');

            $assignment = AgentSync::query()->create([
                'agent_id' => $agent->id,
                'sync_catalog_id' => $catalog->id,
                'sync_recipe_version_id' => $recipeVersionId,
                'status' => $data['status'],
                'interval_seconds' => $data['interval_seconds'],
                'config_version' => 1,
                'config_json' => $data['config'] ?? null,
                'secret_config' => $data['secrets'] ?? null,
            ]);
            $agent->update(['config_version' => $agent->config_version + 1]);

            $this->recordAudit->handle('config', 'assign_agent_sync', $actorId, 'agent_sync', (string) $assignment->id, [
                'agent_code' => $agent->agent_code,
                'sync_code' => $catalog->code,
                'status' => $assignment->status,
                'interval_seconds' => $assignment->interval_seconds,
                'recipe_version_id' => $recipeVersionId,
            ]);

            return $assignment->fresh(['catalog', 'recipeVersion']);
        });
    }
}
