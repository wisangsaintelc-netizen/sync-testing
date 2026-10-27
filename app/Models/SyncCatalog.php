<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\SoftDeletes;

class SyncCatalog extends Model
{
    use SoftDeletes;

    protected $table = 'sync_catalog';

    protected $fillable = [
        'code', 'functional_key', 'direction', 'sync_source_id', 'name', 'source_type', 'min_agent_version', 'enabled_globally',
        'default_interval_seconds', 'description',
    ];

    protected function casts(): array
    {
        return ['enabled_globally' => 'boolean'];
    }

    public function assignments(): HasMany
    {
        return $this->hasMany(AgentSync::class);
    }

    public function source(): BelongsTo
    {
        return $this->belongsTo(SyncSource::class, 'sync_source_id');
    }
}
