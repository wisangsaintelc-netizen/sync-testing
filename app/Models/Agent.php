<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Support\Carbon;

class Agent extends Model
{
    use HasFactory;

    protected $fillable = [
        'client_id', 'agent_code', 'machine_name', 'os', 'version', 'status',
        'last_seen_at', 'last_ip', 'enabled', 'credential_hash', 'config_version',
        'bapps_mysql_config', 'bapps_mysql_configured_at',
    ];

    protected function casts(): array
    {
        return [
            'enabled' => 'boolean',
            'last_seen_at' => 'datetime',
            'bapps_mysql_config' => 'encrypted:array',
            'bapps_mysql_configured_at' => 'datetime',
        ];
    }

    public function client(): BelongsTo
    {
        return $this->belongsTo(Client::class);
    }

    public function syncs(): HasMany
    {
        return $this->hasMany(AgentSync::class);
    }

    public function commands(): HasMany
    {
        return $this->hasMany(SyncCommand::class);
    }

    public function visibleStatus(): string
    {
        if (! $this->enabled || $this->status === 'disabled') {
            return 'disabled';
        }

        if (in_array($this->status, ['enrolled', 'pending_enrollment'], true) && $this->last_seen_at === null) {
            return 'enrolled';
        }

        return $this->last_seen_at?->gte($this->onlineCutoff()) ? 'online' : 'offline';
    }

    public function scopeOnline(Builder $query): void
    {
        $query->where('enabled', true)
            ->where('status', '!=', 'disabled')
            ->where('last_seen_at', '>=', $this->onlineCutoff());
    }

    public function scopeOffline(Builder $query): void
    {
        $query->where('enabled', true)
            ->whereNotIn('status', ['disabled', 'enrolled', 'pending_enrollment'])
            ->where(fn (Builder $agents) => $agents
                ->whereNull('last_seen_at')
                ->orWhere('last_seen_at', '<', $this->onlineCutoff()));
    }

    public function scopeNotOnline(Builder $query): void
    {
        $query->where(fn (Builder $agents) => $agents
            ->where('enabled', false)
            ->orWhere('status', 'disabled')
            ->orWhereIn('status', ['enrolled', 'pending_enrollment'])
            ->orWhereNull('last_seen_at')
            ->orWhere('last_seen_at', '<', $this->onlineCutoff()));
    }

    public function scopeWithVisibleStatus(Builder $query, string $status): void
    {
        match ($status) {
            'online' => $query->online(),
            'offline' => $query->offline(),
            'enrolled' => $query->where('enabled', true)
                ->whereIn('status', ['enrolled', 'pending_enrollment'])
                ->whereNull('last_seen_at'),
            'disabled' => $query->where(fn (Builder $agents) => $agents
                ->where('enabled', false)
                ->orWhere('status', 'disabled')),
        };
    }

    private function onlineCutoff(): Carbon
    {
        return now()->subSeconds((int) config('bapps-sync.agent_online_threshold_seconds'));
    }
}
