<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class SyncAuditEvent extends Model
{
    protected $fillable = [
        'kind', 'action', 'actor_type', 'actor_id', 'target_type', 'target_id', 'result', 'context_json', 'occurred_at',
    ];

    protected function casts(): array
    {
        return ['context_json' => 'array', 'occurred_at' => 'datetime'];
    }
}
