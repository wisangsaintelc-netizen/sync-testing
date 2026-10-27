<?php

namespace App\Http\Controllers\AgentApi;

use App\Actions\AgentApi\ClaimCommands;
use App\Http\Controllers\Controller;
use App\Http\Requests\AgentApi\ClaimCommandsRequest;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentCommandClaimController extends Controller
{
    public function __invoke(ClaimCommandsRequest $request, ClaimCommands $claimCommands): JsonResponse
    {
        /** @var Agent $agent */
        $agent = $request->attributes->get('agent');
        $data = $request->validated();

        if ($data['agent_code'] !== $agent->agent_code) {
            return response()->json(['error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'El agente no puede reclamar comandos ajenos.']], 403);
        }

        return response()->json([
            'data' => $claimCommands->handle($agent, $data['max_commands'], $data['known_command_ids'] ?? []),
        ]);
    }
}
