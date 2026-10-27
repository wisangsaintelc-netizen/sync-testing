<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PublishSyncRecipe;
use App\Actions\ControlApi\RecordControlAudit;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\PublishSyncRecipeRequest;
use App\Models\SyncCatalog;
use Illuminate\Http\JsonResponse;

class SyncRecipeController extends Controller
{
    public function store(PublishSyncRecipeRequest $request, PublishSyncRecipe $publish, RecordControlAudit $audit, string $code): JsonResponse
    {
        $catalog = SyncCatalog::query()->where('code', $code)->firstOrFail();
        $version = $publish->handle($catalog, $request->recipe(), $request->user()?->getKey());
        $audit->handle('config', 'publish_recipe', $request->user()?->getKey(), 'sync_recipe_version', (string) $version->id, [
            'sync_code' => $catalog->code, 'recipe_version' => $version->version, 'payload_hash' => $version->payload_hash,
        ]);

        return response()->json([
            'id' => $version->id, 'version' => $version->version, 'hash' => $version->payload_hash,
            'published_at' => $version->published_at?->toISOString(),
        ], 201);
    }
}
