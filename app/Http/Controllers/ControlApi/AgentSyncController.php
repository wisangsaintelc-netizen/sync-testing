<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\AssignAgentSync;
use App\Actions\ControlApi\UpdateAgentSync;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\StoreAgentSyncRequest;
use App\Http\Requests\ControlApi\UpdateAgentSyncRequest;
use App\Http\Resources\ControlApi\AgentDetailResource;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;
use RuntimeException;

class AgentSyncController extends Controller
{
    public function store(
        StoreAgentSyncRequest $request,
        AssignAgentSync $assignAgentSync,
        string $code,
    ): AgentDetailResource|JsonResponse {
        $agent = Agent::query()->where('agent_code', $code)->first();
        if ($agent === null) {
            return $this->notFound("Agente {$code} no existe.");
        }

        try {
            $assignAgentSync->handle($agent, $request->validated(), $request->user()?->getKey());
        } catch (RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'ASSIGNMENT_REJECTED', 'message' => $exception->getMessage()]], 409);
        }

        return (new AgentDetailResource($agent->fresh()->load(['client', 'syncs.catalog', 'commands.agent'])))
            ->response()
            ->setStatusCode(201);
    }

    public function update(
        UpdateAgentSyncRequest $request,
        UpdateAgentSync $updateAgentSync,
        string $code,
        string $syncCode,
    ): AgentDetailResource|JsonResponse {
        $agent = Agent::query()->where('agent_code', $code)->first();
        if ($agent === null) {
            return $this->notFound("Agente {$code} no existe.");
        }

        $data = $request->validated();
        if ($data === []) {
            return response()->json([
                'error' => ['code' => 'VALIDATION_FAILED', 'message' => 'Indica estado o intervalo para actualizar.'],
            ], 422);
        }

        try {
            $updateAgentSync->handle($agent, $syncCode, $data, $request->user()?->getKey());
        } catch (RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => $exception->getMessage()]], 404);
        }

        return new AgentDetailResource($agent->fresh()->load(['client', 'syncs.catalog', 'commands.agent']));
    }

    private function notFound(string $message): JsonResponse
    {
        return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => $message]], 404);
    }
}
