<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Client extends Model
{
    use HasFactory;

    protected $fillable = ['name', 'system_type', 'status', 'timezone'];

    public function agents(): HasMany
    {
        return $this->hasMany(Agent::class);
    }

    public function nonOnlineAgents(): HasMany
    {
        return $this->hasMany(Agent::class)->notOnline();
    }

    public function runs(): HasMany
    {
        return $this->hasMany(SyncRun::class);
    }

    public function failedRuns(): HasMany
    {
        return $this->runs()->where('status', 'failed')->whereNull('reviewed_at');
    }
}
