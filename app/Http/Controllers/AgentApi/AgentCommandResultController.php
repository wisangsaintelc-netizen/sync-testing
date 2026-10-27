<?php

namespace App\Http\Controllers\AgentApi;

use App\Actions\AgentApi\CompleteCommand;
use App\Http\Controllers\Controller;
use App\Http\Requests\AgentApi\CommandResultRequest;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentCommandResultController extends Controller
{
    public function __invoke(
        CommandResultRequest $request,
        string $commandId,
        CompleteCommand $completeCommand,
    ): JsonResponse {
        /** @var Agent $agent */
        $agent = $request->attributes->get('agent');
        $command = $completeCommand->handle($agent, $commandId, $request->validated());

        return response()->json([
            'command_id' => $command->command_id,
            'status' => $command->status,
            'completed_at' => $command->completed_at?->toISOString(),
            'result' => $command->result_json ?? [],
        ]);
    }
}
