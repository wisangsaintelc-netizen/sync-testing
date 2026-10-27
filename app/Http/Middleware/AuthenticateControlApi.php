<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Symfony\Component\HttpFoundation\Response;

class AuthenticateControlApi
{
    public function handle(Request $request, Closure $next): Response
    {
        $user = Auth::guard('sanctum')->user();

        if (! $user || ! $user->tokenCan('control-api')) {
            return $this->unauthenticated();
        }

        // Los controladores y acciones obtienen al actor desde request()->user().
        // La autenticación se hace explícitamente con Sanctum, por lo que hay que
        // propagar el mismo usuario al resolvedor de la petición.
        $request->setUserResolver(static fn () => $user);

        return $next($request);
    }

    private function unauthenticated(): JsonResponse
    {
        return response()->json([
            'error' => ['code' => 'UNAUTHENTICATED', 'message' => 'Token ausente, inválido o vencido.'],
        ], Response::HTTP_UNAUTHORIZED);
    }
}
