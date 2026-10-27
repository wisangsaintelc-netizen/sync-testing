<?php

namespace App\Http\Resources\ControlApi;

use App\Models\Client;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;
use Illuminate\Support\Carbon;

/** @mixin Client */
class ClientListResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        return [
            'id' => $this->getKey(),
            'name' => $this->name,
            'system' => $this->system_type,
            'agents' => (int) ($this->agents_count ?? 0),
            'syncs' => (int) ($this->getAttribute('syncs_count') ?? 0),
            'health' => $this->health(),
            'health_reason' => $this->healthReason(),
            'last_sync' => ($lastSync = $this->getAttribute('last_sync'))
                ? Carbon::parse($lastSync)->toISOString()
                : null,
            'open_errors' => (int) ($this->getAttribute('open_errors') ?? 0),
        ];
    }

    protected function health(): string
    {
        if ((int) ($this->agents_count ?? 0) === 0) {
            return 'enrolled';
        }
        if ((int) ($this->non_online_agents_count ?? 0) > 0) {
            return 'warning';
        }

        return 'ok';
    }

    protected function healthReason(): ?string
    {
        if ($this->health() !== 'warning') {
            return null;
        }

        $count = (int) ($this->non_online_agents_count ?? 0);
        $agents = $this->resource->relationLoaded('nonOnlineAgents')
            ? $this->nonOnlineAgents->pluck('agent_code')->implode(', ')
            : '';

        if ($agents !== '') {
            return $count === 1
                ? "Agente sin conexión: {$agents}."
                : "{$count} agentes sin conexión: {$agents}.";
        }

        return $count === 1
            ? 'Un agente requiere atención porque no está en línea.'
            : "{$count} agentes requieren atención porque no están en línea.";
    }
}
