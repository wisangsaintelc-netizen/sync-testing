<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use App\Models\SyncCatalog;
use Illuminate\Support\Facades\DB;

final class UpdateSyncCatalog
{
    /**
     * Update a catalog definition. Toggling its global state also versions every
     * affected agent so its next configuration refresh receives the effective state.
     */
    public function handle(SyncCatalog $catalog, array $data): SyncCatalog
    {
        return DB::transaction(function () use ($catalog, $data): SyncCatalog {
            $wasEnabled = $catalog->enabled_globally;
            $catalog->update($data);

            if (array_key_exists('enabled_globally', $data) && $wasEnabled !== $catalog->enabled_globally) {
                Agent::query()
                    ->whereHas('syncs', fn ($syncs) => $syncs->where('sync_catalog_id', $catalog->id))
                    ->increment('config_version');
            }

            return $catalog->fresh();
        });
    }
}
