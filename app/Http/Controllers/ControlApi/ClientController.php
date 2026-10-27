<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Resources\ControlApi\ClientDetailResource;
use App\Http\Resources\ControlApi\ClientListResource;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;

class ClientController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = $this->baseQuery();

        if ($search = $request->validated('search')) {
            $query->where(fn ($clients) => $clients
                ->where('name', 'like', "%{$search}%")
                ->orWhere('system_type', 'like', "%{$search}%"));
        }

        match ($request->validated('health')) {
            'enrolled' => $query->doesntHave('agents'),
            'error' => $query->whereHas('runs', fn ($runs) => $runs->where('status', 'failed')->whereNull('reviewed_at')),
            'warning' => $query->has('agents')->whereHas('agents', fn ($agents) => $agents->notOnline()),
            'ok' => $query->has('agents')->whereDoesntHave('agents', fn ($agents) => $agents->notOnline()),
            default => null,
        };

        return response()->json(PaginatedResponse::make(
            $query->orderBy('name')->paginate($request->pageSize()),
            ClientListResource::class,
        ));
    }

    public function show(int $id): ClientDetailResource|JsonResponse
    {
        $client = $this->baseQuery()
            ->with(['agents' => fn ($agents) => $agents
                ->withCount('syncs')
                ->addSelect(['last_error' => SyncRun::query()
                    ->select('error_code')
                    ->whereColumn('agent_id', 'agents.id')
                    ->whereNotNull('error_code')
                    ->latest('started_at')
                    ->limit(1),
                ])])
            ->with(['runs' => fn ($runs) => $runs
                ->with(['agent.client', 'catalog'])
                ->latest('started_at')
                ->limit(20)])
            ->with(['failedRuns' => fn ($runs) => $runs
                ->with(['agent.client', 'catalog'])
                ->latest('started_at')
                ->limit(10)])
            ->find($id);

        if ($client === null) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => "Cliente {$id} no existe."]], 404);
        }

        return new ClientDetailResource($client);
    }

    private function baseQuery()
    {
        return Client::query()
            ->with(['nonOnlineAgents:id,client_id,agent_code,status,last_seen_at,enabled'])
            ->withCount(['agents', 'agents as non_online_agents_count' => fn ($agents) => $agents->notOnline()])
            ->addSelect([
                'syncs_count' => AgentSync::query()->selectRaw('COUNT(*)')
                    ->whereIn('agent_id', Agent::query()->select('id')->whereColumn('client_id', 'clients.id')),
                'last_sync' => SyncRun::query()->select('finished_at')
                    ->whereColumn('client_id', 'clients.id')
                    ->whereNotNull('finished_at')
                    ->latest('finished_at')
                    ->limit(1),
                'open_errors' => SyncRun::query()->selectRaw('COUNT(*)')
                    ->whereColumn('client_id', 'clients.id')
                    ->where('status', 'failed')
                    ->whereNull('reviewed_at'),
            ]);
    }
}
