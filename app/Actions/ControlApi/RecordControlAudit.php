<?php

namespace App\Actions\ControlApi;

use App\Models\SyncAuditEvent;

final class RecordControlAudit
{
    /**
     * Persist an operator-visible audit event. Context must never contain
     * credentials or other secret configuration values.
     */
    public function handle(
        string $kind,
        string $action,
        ?int $actorId,
        string $targetType,
        string $targetId,
        array $context = [],
    ): SyncAuditEvent {
        return SyncAuditEvent::query()->create([
            'kind' => $kind,
            'action' => $action,
            'actor_type' => 'user',
            'actor_id' => $actorId,
            'target_type' => $targetType,
            'target_id' => $targetId,
            'result' => 'success',
            'context_json' => $context,
            'occurred_at' => now(),
        ]);
    }
}
