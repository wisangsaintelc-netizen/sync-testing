<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Resources\ControlApi\AuditEventResource;
use App\Models\SyncAuditEvent;
use Illuminate\Http\JsonResponse;

class AuditController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = SyncAuditEvent::query();

        if ($kind = $request->validated('kind')) {
            $query->where('kind', $kind);
        }
        if ($search = $request->validated('search')) {
            $query->where(fn ($events) => $events
                ->where('action', 'like', "%{$search}%")
                ->orWhere('target_type', 'like', "%{$search}%")
                ->orWhere('target_id', 'like', "%{$search}%")
                ->orWhere('result', 'like', "%{$search}%"));
        }

        return response()->json(PaginatedResponse::make(
            $query->latest('occurred_at')->paginate($request->pageSize()),
            AuditEventResource::class,
        ));
    }
}
