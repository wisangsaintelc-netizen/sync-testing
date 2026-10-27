<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncCatalog;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin SyncCatalog */
class SyncCatalogResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        return [
            'name' => $this->name,
            'code' => $this->code,
            'direction' => $this->direction ?? 'read',
            'source_id' => $this->sync_source_id,
            'source' => $this->source?->label ?? $this->source_type,
            'min_version' => $this->min_agent_version,
            'enabled' => $this->enabled_globally,
            'key' => $this->functional_key ?? $this->code,
            'desc' => $this->description ?? '',
            'interval_seconds' => $this->default_interval_seconds,
        ];
    }
}
