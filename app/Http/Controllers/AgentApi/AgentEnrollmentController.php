<?php

namespace App\Http\Controllers\AgentApi;

use App\Actions\AgentApi\EnrollAgent;
use App\Http\Controllers\Controller;
use App\Http\Requests\AgentApi\EnrollAgentRequest;
use Illuminate\Http\JsonResponse;

class AgentEnrollmentController extends Controller
{
    public function __invoke(EnrollAgentRequest $request, EnrollAgent $enrollAgent): JsonResponse
    {
        return response()->json($enrollAgent->handle($request->validated()), 201);
    }
}
