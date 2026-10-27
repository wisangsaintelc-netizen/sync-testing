<?php

namespace App\Http\Middleware;

use App\Models\Agent;
use Closure;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Hash;
use Symfony\Component\HttpFoundation\Response;

class AuthenticateAgent
{
    public function handle(Request $request, Closure $next): Response
    {
        $agentCode = $request->header(config('bapps-sync.agent_header'));
        $token = $request->bearerToken();

        if (! is_string($agentCode) || $agentCode === '' || ! is_string($token) || $token === '') {
            return response()->json(['error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'Credencial de agente requerida.']], 401);
        }

        $agent = Agent::query()->where('agent_code', $agentCode)->first();

        if ($agent === null || ! $agent->enabled || ! Hash::check($token, $agent->credential_hash)) {
            return response()->json(['error' => ['code' => 'AUTHENTICATION_FAILED', 'message' => 'Credencial de agente inválida.']], 401);
        }

        $request->attributes->set('agent', $agent);

        return $next($request);
    }
}
