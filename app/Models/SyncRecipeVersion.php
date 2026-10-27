<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SyncRecipeVersion extends Model
{
    protected $fillable = [
        'sync_recipe_id', 'version', 'payload_json', 'payload_hash', 'published_by', 'published_at',
    ];

    protected function casts(): array
    {
        return ['payload_json' => 'array', 'published_at' => 'datetime'];
    }

    public function recipe(): BelongsTo
    {
        return $this->belongsTo(SyncRecipe::class, 'sync_recipe_id');
    }
}
