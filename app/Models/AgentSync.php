<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class AgentSync extends Model
{
    protected $fillable = [
        'agent_id', 'sync_catalog_id', 'sync_recipe_version_id', 'status', 'interval_seconds',
        'config_version', 'config_json', 'secret_config', 'next_run_hint',
    ];

    protected function casts(): array
    {
        return [
            'config_json' => 'array',
            'secret_config' => 'encrypted:array',
            'next_run_hint' => 'datetime',
        ];
    }

    public function agent(): BelongsTo
    {
        return $this->belongsTo(Agent::class);
    }

    public function catalog(): BelongsTo
    {
        return $this->belongsTo(SyncCatalog::class, 'sync_catalog_id');
    }

    public function recipeVersion(): BelongsTo
    {
        return $this->belongsTo(SyncRecipeVersion::class, 'sync_recipe_version_id');
    }
}
