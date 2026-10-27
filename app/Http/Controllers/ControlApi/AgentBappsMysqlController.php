<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\ConfigureAgentBappsMysql;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\UpdateAgentBappsMysqlRequest;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentBappsMysqlController extends Controller
{
    public function update(
        UpdateAgentBappsMysqlRequest $request,
        ConfigureAgentBappsMysql $configure,
        string $code,
    ): JsonResponse {
        $agent = Agent::query()->where('agent_code', $code)->first();

        if ($agent === null) {
            return response()->json([
                'error' => ['code' => 'NOT_FOUND', 'message' => "Agente {$code} no existe."],
            ], 404);
        }

        $agent = $configure->handle($agent, $request->validated());
        $target = $agent->bapps_mysql_config;

        return response()->json([
            'agent_code' => $agent->agent_code,
            'config_version' => $agent->config_version,
            'bapps_mysql' => [
                'host' => $target['host'],
                'port' => $target['port'],
                'database' => $target['database'],
                'username' => $target['username'],
                'configured_at' => $agent->bapps_mysql_configured_at?->toISOString(),
            ],
        ]);
    }
}
