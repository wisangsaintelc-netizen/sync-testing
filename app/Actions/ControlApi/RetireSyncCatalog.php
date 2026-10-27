<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\SyncCatalog;
use Illuminate\Support\Facades\DB;
use RuntimeException;

final class RetireSyncCatalog
{
    public function __construct(private readonly RecordControlAudit $recordAudit) {}

    /**
     * Retire a globally disabled catalog without destroying its execution history.
     */
    public function handle(SyncCatalog $catalog, ?int $actorId = null): void
    {
        DB::transaction(function () use ($catalog, $actorId): void {
            $catalog = SyncCatalog::query()->lockForUpdate()->findOrFail($catalog->id);
            if ($catalog->enabled_globally) {
                throw new RuntimeException('Deshabilita el sincronizador antes de eliminarlo.');
            }

            $agentIds = AgentSync::query()
                ->where('sync_catalog_id', $catalog->id)
                ->lockForUpdate()
                ->pluck('agent_id')
                ->unique()
                ->values();
            $assignmentsRemoved = AgentSync::query()
                ->where('sync_catalog_id', $catalog->id)
                ->delete();

            if ($agentIds->isNotEmpty()) {
                Agent::query()->whereIn('id', $agentIds)->increment('config_version');
            }

            $code = $catalog->code;
            $catalog->delete();
            $this->recordAudit->handle('config', 'delete_catalog', $actorId, 'sync_catalog', $code, [
                'sync_code' => $code,
                'assignments_removed' => $assignmentsRemoved,
                'history_retained' => true,
            ]);
        });
    }
}
