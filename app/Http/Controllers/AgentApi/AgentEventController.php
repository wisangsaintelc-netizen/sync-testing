<?php

namespace App\Http\Controllers\AgentApi;

use App\Actions\AgentApi\ProjectAgentEvent;
use App\Http\Controllers\Controller;
use App\Http\Requests\AgentApi\AgentEventRequest;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentEventController extends Controller
{
    public function __invoke(AgentEventRequest $request, ProjectAgentEvent $projectEvent): JsonResponse
    {
        /** @var Agent $agent */
        $agent = $request->attributes->get('agent');
        $data = $request->validated();

        if ($data['agent_code'] !== $agent->agent_code) {
            return response()->json(['error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'El agente no puede registrar eventos ajenos.']], 403);
        }

        $result = $projectEvent->handle($agent, $data);

        return response()->json([
            'acknowledged' => true,
            'duplicate' => $result['duplicate'],
        ]);
    }
}
