<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncCommand;
use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin SyncCommand */
class CommandResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        $actor = $this->created_by ? User::find($this->created_by)?->email : null;

        return [
            'id' => $this->command_id,
            'type' => $this->command_type,
            'agent' => $this->agent?->agent_code ?? '',
            'by' => $actor ?? 'sistema',
            'created_at' => $this->issued_at?->toISOString(),
            'status' => $this->status,
            'result' => $this->result_json,
            'expires_at' => $this->expires_at?->toISOString(),
            'sync_code' => $this->sync_code,
            'run_id' => $this->run_id,
        ];
    }
}
