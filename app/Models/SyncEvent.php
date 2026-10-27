<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncEvent extends Model
{
    protected $fillable = [
        'event_id', 'schema_version', 'event_type', 'agent_id', 'client_id',
        'sync_code', 'run_id', 'correlation_id', 'occurred_at', 'received_at', 'payload_json',
    ];

    protected function casts(): array
    {
        return ['occurred_at' => 'datetime', 'received_at' => 'datetime', 'payload_json' => 'array'];
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(Agent::class);
    }
}
