<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class SyncRecipe extends Model
{
    protected $fillable = ['sync_catalog_id'];

    public function catalog(): BelongsTo
    {
        return $this->belongsTo(SyncCatalog::class, 'sync_catalog_id');
    }

    public function versions(): HasMany
    {
        return $this->hasMany(SyncRecipeVersion::class);
    }
}
