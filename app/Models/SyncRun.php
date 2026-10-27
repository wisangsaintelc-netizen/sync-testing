<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncRun extends Model
{
    protected $fillable = [
        'run_id', 'agent_id', 'client_id', 'sync_catalog_id', 'correlation_id',
        'status', 'trigger', 'command_id', 'started_at', 'finished_at', 'duration_ms',
        'rows_read', 'rows_inserted', 'rows_updated', 'rows_deleted', 'rows_failed',
        'error_code', 'error_message', 'agent_version', 'reviewed_by', 'reviewed_at',
    ];

    protected function casts(): array
    {
        return ['started_at' => 'datetime', 'finished_at' => 'datetime', 'reviewed_at' => 'datetime'];
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(Agent::class);
    }

    public function catalog(): BelongsTo
    {
        return $this->belongsTo(SyncCatalog::class, 'sync_catalog_id')->withTrashed();
    }
}
