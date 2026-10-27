<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Actions\ControlApi\PublishSyncRecipe;
use App\Actions\ControlApi\RecordControlAudit;
use App\Actions\ControlApi\RetireSyncCatalog;
use App\Actions\ControlApi\UpdateSyncCatalog;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Requests\ControlApi\StoreSyncCatalogRequest;
use App\Http\Requests\ControlApi\UpdateSyncCatalogRequest;
use App\Http\Resources\ControlApi\SyncCatalogResource;
use App\Models\SyncCatalog;
use App\Models\SyncSource;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

class SyncCatalogController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = SyncCatalog::query()->with('source');

        if ($status = $request->validated('status')) {
            if (in_array($status, ['enabled', 'disabled'], true)) {
                $query->where('enabled_globally', $status === 'enabled');
            }
        }

        if ($search = $request->validated('search')) {
            $query->where(fn ($syncs) => $syncs
                ->where('code', 'like', "%{$search}%")
                ->orWhere('name', 'like', "%{$search}%")
                ->orWhere('source_type', 'like', "%{$search}%")
                ->orWhereHas('source', fn ($source) => $source
                    ->where('system_name', 'like', "%{$search}%")
                    ->orWhere('system_version', 'like', "%{$search}%")
                    ->orWhere('database_engine', 'like', "%{$search}%")));
        }

        return response()->json(PaginatedResponse::make(
            $query->orderBy('code')->paginate($request->pageSize()),
            SyncCatalogResource::class,
        ));
    }

    public function store(
        StoreSyncCatalogRequest $request,
        PublishSyncRecipe $publishRecipe,
        RecordControlAudit $recordAudit,
    ): JsonResponse {
        $data = $request->validated();
        $source = SyncSource::query()->findOrFail($data['source_id']);
        $recipe = $data['recipe'] ?? null;
        unset($data['recipe']);
        if (
            $recipe !== null
            && ($recipe['engine'] ?? null) === 'declarative_table_reader'
            && $recipe['source']['driver'] !== $this->recipeDriverFor($source->database_engine)
        ) {
            throw ValidationException::withMessages([
                'recipe.source.driver' => 'El motor de la receta no coincide con la fuente seleccionada.',
            ]);
        }
        if (
            $recipe !== null
            && ($recipe['engine'] ?? null) === 'valery_prs_writer_v1'
            && $this->recipeDriverFor($source->database_engine) !== 'firebird'
        ) {
            throw ValidationException::withMessages([
                'source_id' => 'El escritor de presupuestos Valery requiere una fuente Firebird.',
            ]);
        }
        $data['sync_source_id'] = $data['source_id'];
        unset($data['source_id']);
        $data['source_type'] = $source->label;

        $catalog = DB::transaction(function () use ($data, $recipe, $request, $publishRecipe, $recordAudit): SyncCatalog {
            $catalog = SyncCatalog::query()->create($data);
            $actorId = $request->user()?->getKey();
            $recordAudit->handle('config', 'create_catalog', $actorId, 'sync_catalog', $catalog->code, [
                'sync_code' => $catalog->code,
                'recipe_published' => $recipe !== null,
            ]);
            if ($recipe !== null) {
                $version = $publishRecipe->handle($catalog, $recipe, $actorId);
                $recordAudit->handle('config', 'publish_recipe', $actorId, 'sync_recipe_version', (string) $version->id, [
                    'sync_code' => $catalog->code,
                    'recipe_version' => $version->version,
                    'payload_hash' => $version->payload_hash,
                ]);
            }

            return $catalog;
        })->load('source');

        return (new SyncCatalogResource($catalog))->response()->setStatusCode(201);
    }

    private function recipeDriverFor(string $databaseEngine): ?string
    {
        $normalized = strtolower($databaseEngine);

        return match (true) {
            str_contains($normalized, 'firebird') => 'firebird',
            str_contains($normalized, 'sql server'), str_contains($normalized, 'sqlserver') => 'sqlserver',
            default => null,
        };
    }

    public function update(
        UpdateSyncCatalogRequest $request,
        UpdateSyncCatalog $updateSyncCatalog,
        RecordControlAudit $recordAudit,
        string $code,
    ): SyncCatalogResource|JsonResponse {
        $catalog = SyncCatalog::query()->where('code', $code)->first();
        if ($catalog === null) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => "Sincronizador {$code} no existe."]], 404);
        }

        $data = $request->catalogData();
        if ($data === []) {
            return response()->json([
                'error' => ['code' => 'VALIDATION_FAILED', 'message' => 'Indica al menos un campo editable.'],
            ], 422);
        }

        if (array_key_exists('sync_source_id', $data)) {
            $data['source_type'] = SyncSource::query()->findOrFail($data['sync_source_id'])->label;
        }

        $catalog = $updateSyncCatalog->handle($catalog, $data)->load('source');
        $recordAudit->handle('config', 'update_catalog', $request->user()?->getKey(), 'sync_catalog', $catalog->code, [
            'sync_code' => $catalog->code,
            'fields' => array_keys($data),
        ]);

        return new SyncCatalogResource($catalog);
    }

    public function destroy(
        RetireSyncCatalog $retireSyncCatalog,
        string $code,
    ): JsonResponse|Response {
        $catalog = SyncCatalog::query()->where('code', $code)->first();
        if ($catalog === null) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => "Sincronizador {$code} no existe."]], 404);
        }

        try {
            $retireSyncCatalog->handle($catalog, request()->user()?->getKey());
        } catch (\RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'CATALOG_ENABLED', 'message' => $exception->getMessage()]], 409);
        }

        return response()->noContent();
    }
}
