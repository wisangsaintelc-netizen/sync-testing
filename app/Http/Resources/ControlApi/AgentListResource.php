<?php

namespace App\Http\Resources\ControlApi;

use App\Models\Agent;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin Agent */
class AgentListResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        return [
            'code' => $this->agent_code,
            'client' => $this->client?->name ?? '',
            'machine' => $this->machine_name ?? '',
            'version' => $this->version ?? '',
            'status' => $this->visibleStatus(),
            'last_heartbeat' => $this->last_seen_at?->toISOString(),
            'ip' => $this->last_ip ?? '',
            'syncs_count' => (int) ($this->syncs_count ?? 0),
            'last_error' => $this->getAttribute('last_error'),
        ];
    }
}
