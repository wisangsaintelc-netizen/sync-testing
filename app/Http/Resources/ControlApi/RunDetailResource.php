<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncRun;
use Illuminate\Http\Request;

/** @mixin SyncRun */
class RunDetailResource extends RunListResource
{
    public function toArray(Request $request): array
    {
        return [
            ...parent::toArray($request),
            'correlation_id' => $this->correlation_id,
            'timeline' => $this->timeline ?? [
                ['event' => 'run_started', 'detail' => 'Ejecución iniciada', 'at' => $this->started_at?->toISOString()],
                ...($this->finished_at ? [['event' => 'run_finished', 'detail' => 'Ejecución finalizada', 'at' => $this->finished_at->toISOString()]] : []),
            ],
            'tech_message' => $this->error_message,
        ];
    }
}
