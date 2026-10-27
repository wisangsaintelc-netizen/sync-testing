<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\SyncRecipeVersion;
use Illuminate\Support\Facades\DB;
use RuntimeException;

final class UpdateAgentSync
{
    public function __construct(private readonly RecordControlAudit $recordAudit) {}

    public function handle(Agent $agent, string $syncCode, array $data, ?int $actorId = null): AgentSync
    {
        return DB::transaction(function () use ($agent, $syncCode, $data, $actorId): AgentSync {
            $assignment = AgentSync::query()
                ->where('agent_id', $agent->id)
                ->whereHas('catalog', fn ($query) => $query->where('code', $syncCode))
                ->lockForUpdate()
                ->first();

            if ($assignment === null) {
                throw new RuntimeException("El sincronizador {$syncCode} no está asignado a {$agent->agent_code}.");
            }

            $recipeVersionId = $data['sync_recipe_version_id'] ?? null;
            if ($recipeVersionId !== null) {
                $recipeVersion = SyncRecipeVersion::query()
                    ->whereKey($recipeVersionId)
                    ->whereHas('recipe', fn ($recipe) => $recipe->where('sync_catalog_id', $assignment->sync_catalog_id))
                    ->first();
                if ($recipeVersion === null) {
                    throw new RuntimeException('La versión de receta no pertenece a este sincronizador.');
                }
            }

            $assignment->update([
                ...array_key_exists('status', $data) ? ['status' => $data['status']] : [],
                ...array_key_exists('interval_seconds', $data) ? ['interval_seconds' => $data['interval_seconds']] : [],
                ...($recipeVersionId !== null ? ['sync_recipe_version_id' => $recipeVersionId] : []),
                'config_version' => $assignment->config_version + 1,
            ]);
            $agent->update(['config_version' => $agent->config_version + 1]);

            $this->recordAudit->handle('config', 'update_agent_sync', $actorId, 'agent_sync', (string) $assignment->id, [
                'agent_code' => $agent->agent_code,
                'sync_code' => $syncCode,
                'fields' => array_keys($data),
            ]);

            return $assignment->fresh(['catalog']);
        });
    }
}
