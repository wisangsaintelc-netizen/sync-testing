<?php

namespace App\Actions\ControlApi;

use App\Models\SyncCatalog;
use App\Models\SyncRecipe;
use App\Models\SyncRecipeVersion;
use Illuminate\Support\Facades\DB;

final class PublishSyncRecipe
{
    public function handle(SyncCatalog $catalog, array $payload, ?int $actorId): SyncRecipeVersion
    {
        return DB::transaction(function () use ($catalog, $payload, $actorId): SyncRecipeVersion {
            $recipe = SyncRecipe::query()->firstOrCreate(['sync_catalog_id' => $catalog->id]);
            $recipe = SyncRecipe::query()->whereKey($recipe->id)->lockForUpdate()->firstOrFail();
            $version = (int) $recipe->versions()->max('version') + 1;
            $payload['recipe_version'] = $version;
            $json = json_encode($payload, JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION);

            return $recipe->versions()->create([
                'version' => $version,
                'payload_json' => $payload,
                'payload_hash' => 'sha256:'.hash('sha256', $json),
                'published_by' => $actorId,
                'published_at' => now(),
            ]);
        });
    }
}
