<?php

namespace App\Http\Resources\ControlApi;

use Illuminate\Http\Request;

class ClientDetailResource extends ClientListResource
{
    public function toArray(Request $request): array
    {
        return [
            ...parent::toArray($request),
            'agents_list' => $this->agents->map(fn ($agent) => [
                'code' => $agent->agent_code,
                'client' => $this->name,
                'machine' => $agent->machine_name ?? '',
                'version' => $agent->version ?? '',
                'status' => $agent->visibleStatus(),
                'last_heartbeat' => $agent->last_seen_at?->toISOString(),
                'ip' => $agent->last_ip ?? '',
                'syncs_count' => (int) ($agent->syncs_count ?? 0),
                'last_error' => $agent->getAttribute('last_error'),
            ])->values()->all(),
            'runs' => RunListResource::collection($this->runs)->resolve(),
            'errors' => RunListResource::collection($this->failedRuns)->resolve(),
        ];
    }
}
