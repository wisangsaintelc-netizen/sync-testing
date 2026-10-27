<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Actions\ControlApi\RecordControlAudit;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Requests\ControlApi\StoreSyncSourceRequest;
use App\Http\Requests\ControlApi\UpdateSyncSourceRequest;
use App\Http\Resources\ControlApi\SyncSourceResource;
use App\Models\SyncSource;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\DB;

class SyncSourceController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = SyncSource::query()->withCount('catalogs');

        if ($search = $request->validated('search')) {
            $query->where(fn ($sources) => $sources
                ->where('system_name', 'like', "%{$search}%")
                ->orWhere('system_version', 'like', "%{$search}%")
                ->orWhere('database_engine', 'like', "%{$search}%"));
        }

        return response()->json(PaginatedResponse::make(
            $query->orderBy('system_name')->orderBy('system_version')->orderBy('database_engine')
                ->paginate($request->pageSize()),
            SyncSourceResource::class,
        ));
    }

    public function store(StoreSyncSourceRequest $request, RecordControlAudit $recordAudit): JsonResponse
    {
        $source = SyncSource::query()->create($request->validated())->loadCount('catalogs');
        $recordAudit->handle('config', 'create_sync_source', $request->user()?->getKey(), 'sync_source', (string) $source->id, [
            'label' => $source->label,
        ]);

        return (new SyncSourceResource($source))->response()->setStatusCode(201);
    }

    public function update(
        UpdateSyncSourceRequest $request,
        RecordControlAudit $recordAudit,
        int $id,
    ): SyncSourceResource|JsonResponse {
        $source = SyncSource::query()->find($id);
        if ($source === null) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => 'La fuente no existe.']], 404);
        }

        $data = $request->validated();
        if ($data === []) {
            return response()->json(['error' => ['code' => 'VALIDATION_FAILED', 'message' => 'Indica al menos un campo editable.']], 422);
        }

        $source->update($data);
        $recordAudit->handle('config', 'update_sync_source', $request->user()?->getKey(), 'sync_source', (string) $source->id, [
            'label' => $source->label,
            'fields' => array_keys($data),
        ]);

        return new SyncSourceResource($source->fresh()->loadCount('catalogs'));
    }

    public function destroy(int $id, RecordControlAudit $recordAudit): JsonResponse|Response
    {
        return DB::transaction(function () use ($id, $recordAudit): JsonResponse|Response {
            $source = SyncSource::query()->lockForUpdate()->find($id);
            if ($source === null) {
                return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => 'La fuente no existe.']], 404);
            }

            if ($source->catalogs()->exists()) {
                return response()->json([
                    'error' => ['code' => 'SOURCE_IN_USE', 'message' => 'No se puede eliminar una fuente con sincronizadores asociados.'],
                ], 409);
            }

            $label = $source->label;
            $source->delete();
            $recordAudit->handle('config', 'delete_sync_source', request()->user()?->getKey(), 'sync_source', (string) $id, [
                'label' => $label,
            ]);

            return response()->noContent();
        });
    }
}
