<?php

namespace App\Http\Controllers\ControlApi;

use App\Actions\ControlApi\PaginatedResponse;
use App\Actions\ControlApi\RetryFailedRun;
use App\Actions\ControlApi\ReviewFailedRun;
use App\Http\Controllers\Controller;
use App\Http\Requests\ControlApi\ListRequest;
use App\Http\Resources\ControlApi\RunDetailResource;
use App\Http\Resources\ControlApi\RunListResource;
use App\Models\SyncRun;
use Illuminate\Http\JsonResponse;
use RuntimeException;

class RunController extends Controller
{
    public function index(ListRequest $request): JsonResponse
    {
        $query = SyncRun::query()->with(['agent.client', 'catalog']);

        if ($status = $request->validated('status')) {
            $query->where('status', $status);
        }

        if ($trigger = $request->query('trigger')) {
            $query->where('trigger', $trigger);
        }

        if ($search = $request->validated('search')) {
            $query->where(function ($query) use ($search): void {
                $query->where('run_id', 'like', "%{$search}%")
                    ->orWhere('error_code', 'like', "%{$search}%")
                    ->orWhereHas('agent', fn ($agents) => $agents->where('agent_code', 'like', "%{$search}%")
                        ->orWhereHas('client', fn ($clients) => $clients->where('name', 'like', "%{$search}%")))
                    ->orWhereHas('catalog', fn ($catalog) => $catalog->where('code', 'like', "%{$search}%"));
            });
        }

        return response()->json(PaginatedResponse::make($query->latest('started_at')->paginate($request->pageSize()), RunListResource::class));
    }

    public function show(string $id): RunDetailResource|JsonResponse
    {
        $run = SyncRun::query()->where('run_id', $id)->with(['agent.client', 'catalog'])->first();

        if (! $run) {
            return response()->json(['error' => ['code' => 'NOT_FOUND', 'message' => "Ejecución {$id} no existe."]], 404);
        }

        return new RunDetailResource($run);
    }

    public function retry(string $id, RetryFailedRun $retryFailedRun): RunListResource|JsonResponse
    {
        try {
            return new RunListResource($retryFailedRun->handle($id, request()->user()?->getKey()));
        } catch (RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'RETRY_REJECTED', 'message' => $exception->getMessage()]], 409);
        }
    }

    public function review(string $id, ReviewFailedRun $reviewFailedRun): RunListResource|JsonResponse
    {
        try {
            return new RunListResource($reviewFailedRun->handle($id, request()->user()?->getKey()));
        } catch (RuntimeException $exception) {
            return response()->json(['error' => ['code' => 'REVIEW_REJECTED', 'message' => $exception->getMessage()]], 409);
        }
    }
}
