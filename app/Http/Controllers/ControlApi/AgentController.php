<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Resources\ControlApi\AgentDetailResource;
use App\Http\Resources\ControlApi\AgentListResource;
use App\Models\Agent;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;

class AgentController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = Agent::query()
            ->with('client')
            ->withCount('syncs')
            ->addSelect(['last_error' => SyncRun::query()
                ->select('error_code')
                ->whereColumn('agent_id', 'agents.id')
                ->whereNotNull('error_code')
                ->latest('started_at')
                ->limit(1),
            ]);

        if ($status = $request->validated('status')) {
            $query->withVisibleStatus($status);
        }

        if ($search = $request->validated('search')) {
            $query->where(function ($query) use ($search): void {
                $query->where('agent_code', 'like', "%{$search}%")
                    ->orWhere('machine_name', 'like', "%{$search}%")
                    ->orWhere('last_ip', 'like', "%{$search}%")
                    ->orWhereHas('client', fn ($clients) => $clients->where('name', 'like', "%{$search}%"));
            });
        }

        return response()->json(PaginatedResponse::make($query->orderBy('agent_code')->paginate($request->pageSize()), AgentListResource::class));
    }

    public function show(string $code): AgentDetailResource|JsonResponse
    {
        $agent = Agent::query()
            ->where('agent_code', $code)
            ->with(['client', 'syncs.catalog.source', 'commands.agent'])
            ->withCount('syncs')
            ->first();

        if (! $agent) {
            return $this->notFound("Agente {$code} no existe.");
        }

        return new AgentDetailResource($agent);
    }

    private function notFound(string $message): JsonResponse
    {
        return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => $message]], 404);
    }
}
