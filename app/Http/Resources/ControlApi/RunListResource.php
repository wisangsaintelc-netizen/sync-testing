<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncRun;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin SyncRun */
class RunListResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        return [
            'id' => $this->run_id,
            'client' => $this->agent?->client?->name ?? '',
            'agent' => $this->agent?->agent_code ?? '',
            'sync' => $this->catalog?->code ?? '',
            'status' => $this->status,
            'trigger' => $this->trigger ?? 'schedule',
            'started_at' => $this->started_at?->toISOString(),
            'ended_at' => $this->finished_at?->toISOString(),
            'rows_read' => $this->rows_read,
            'rows_inserted' => $this->rows_inserted,
            'rows_updated' => $this->rows_updated,
            'rows_failed' => $this->rows_failed,
            'error' => $this->error_code,
            'reviewed_at' => $this->reviewed_at?->toISOString(),
            'reviewed_by' => $this->reviewed_by,
        ];
    }
}
