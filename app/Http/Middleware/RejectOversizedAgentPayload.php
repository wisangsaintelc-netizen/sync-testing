<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class RejectOversizedAgentPayload
{
    public function handle(Request $request, Closure $next): Response
    {
        $limit = (int) config('bapps-sync.agent_max_request_bytes');
        $contentLength = $request->header('Content-Length');
        $isTooLarge = is_numeric($contentLength) && (int) $contentLength > $limit;

        if ($isTooLarge || strlen($request->getContent()) > $limit) {
            return $this->payloadTooLarge();
        }

        return $next($request);
    }

    private function payloadTooLarge(): JsonResponse
    {
        return response()->json([
            'error' => [
                'code' => 'PAYLOAD_TOO_LARGE',
                'message' => 'La solicitud del agente excede el tamaño permitido.',
            ],
        ], Response::HTTP_REQUEST_ENTITY_TOO_LARGE);
    }
}
