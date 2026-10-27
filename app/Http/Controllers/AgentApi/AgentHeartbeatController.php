<?php

namespace App\Http\Controllers\AgentApi;

use App\Http\Controllers\Controller;
use App\Http\Requests\AgentApi\HeartbeatRequest;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentHeartbeatController extends Controller
{
    public function __invoke(HeartbeatRequest $request): JsonResponse
    {
        /** @var Agent $agent */
        $agent = $request->attributes->get('agent');
        $data = $request->validated();

        if ($data['agent_code'] !== $agent->agent_code) {
            return response()->json(['error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'El agente no puede reportar por otro código.']], 403);
        }

        $agent->update([
            'machine_name' => $data['machine_name'],
            'version' => $data['agent_version'],
            'status' => 'online',
            'last_seen_at' => now(),
            'last_ip' => $request->ip(),
        ]);

        $hasPendingCommands = $agent->commands()
            ->where('status', 'pending')
            ->where('expires_at', '>', now())
            ->exists();

        return response()->json([
            'acknowledged' => true,
            'latest_config_version' => $agent->config_version,
            'has_pending_commands' => $hasPendingCommands,
            'server_time' => now()->toISOString(),
        ]);
    }
}
