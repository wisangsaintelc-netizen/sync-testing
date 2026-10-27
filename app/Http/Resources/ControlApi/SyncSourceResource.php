<?php

namespace App\Http\Resources\ControlApi;

use App\Models\SyncSource;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

/** @mixin SyncSource */
class SyncSourceResource extends JsonResource
{
    public static $wrap = null;

    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'system_name' => $this->system_name,
            'system_version' => $this->system_version,
            'database_engine' => $this->database_engine,
            'label' => $this->label,
            'enabled' => $this->enabled,
            'syncs_count' => $this->catalogs_count ?? 0,
        ];
    }
}
