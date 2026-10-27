<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class SyncSource extends Model
{
    protected $fillable = [
        'system_name',
        'system_version',
        'database_engine',
        'enabled',
    ];

    protected function casts(): array
    {
        return ['enabled' => 'boolean'];
    }

    public function catalogs(): HasMany
    {
        return $this->hasMany(SyncCatalog::class);
    }

    public function getLabelAttribute(): string
    {
        $system = trim(implode(' ', array_filter([$this->system_name, $this->system_version])));

        return $system === '' ? $this->database_engine : "{$system} / {$this->database_engine}";
    }
}
