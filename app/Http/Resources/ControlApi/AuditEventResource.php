<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncAuditEvent;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin SyncAuditEvent */
class AuditEventResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        $context = $this->context_json ?? [];

        return [
            'id' => (string) $this->getKey(),
            'kind' => $this->kind,
            'action' => $this->action,
            'actor' => $this->actor_type.($this->actor_id ? ':'.$this->actor_id : ''),
            'target' => $this->target_type.':'.$this->target_id,
            'ctx' => $context['sync_code'] ?? $context['run_id'] ?? '—',
            'result' => $this->result,
            'at' => $this->occurred_at?->toISOString(),
        ];
    }
}
