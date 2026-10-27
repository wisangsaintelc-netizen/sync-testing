<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncCommand extends Model
{
    protected $fillable = [
        'command_id', 'agent_id', 'command_type', 'sync_code', 'run_id',
        'payload_json', 'status', 'idempotency_key', 'created_by', 'issued_at',
        'expires_at', 'claimed_at', 'lease_expires_at', 'completed_at', 'result_json',
    ];

    protected function casts(): array
    {
        return [
            'payload_json' => 'array',
            'result_json' => 'array',
            'issued_at' => 'datetime',
            'expires_at' => 'datetime',
            'claimed_at' => 'datetime',
            'lease_expires_at' => 'datetime',
            'completed_at' => 'datetime',
        ];
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(Agent::class);
    }
}
