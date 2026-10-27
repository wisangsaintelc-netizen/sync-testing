<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\QueueAgentCommand;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\StoreAgentCommandRequest;
use App\Http\Resources\ControlApi\CommandResource;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;
use RuntimeException;

class AgentCommandController extends Controller
{
    public function store(StoreAgentCommandRequest $request, QueueAgentCommand $queueCommand, string $code): CommandResource|JsonResponse
    {
        $agent = Agent::query()->where('agent_code', $code)->first();
        if ($agent === null) {
            return $this->notFound("Agente {$code} no existe.");
        }

        try {
            $command = $queueCommand->handle($agent, $request->validated(), $request->user()?->getKey());
        } catch (RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'COMMAND_REJECTED', 'message' => $exception->getMessage()]], 409);
        }

        return (new CommandResource($command->load('agent')))->response()->setStatusCode(201);
    }

    public function show(string $code, string $commandId): CommandResource|JsonResponse
    {
        $agent = Agent::query()->where('agent_code', $code)->first();
        if ($agent === null) {
            return $this->notFound("Agente {$code} no existe.");
        }

        $command = $agent->commands()->where('command_id', $commandId)->first();
        if ($command === null) {
            return $this->notFound("Comando {$commandId} no existe para {$code}.");
        }
        if (
            $command->command_type === 'inspect_source_table'
            && $command->expires_at?->isPast()
            && $command->result_json !== null
        ) {
            $command->update(['result_json' => null]);
        }

        return new CommandResource($command->load('agent'));
    }

    private function notFound(string $message): JsonResponse
    {
        return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => $message]], 404);
    }
}
