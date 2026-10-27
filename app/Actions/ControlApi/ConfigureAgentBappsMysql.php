<?php

namespace App\Actions\ControlApi;

use App\Models\Agent;
use Illuminate\Support\Facades\DB;

final class ConfigureAgentBappsMysql
{
    /**
     * Stores the target encrypted by Laravel's encrypted:array cast and publishes
     * a new configuration version for the selected agent only.
     */
    public function handle(Agent $agent, array $target): Agent
    {
        return DB::transaction(function () use ($agent, $target): Agent {
            $agent->update([
                'bapps_mysql_config' => [
                    'host' => $target['host'],
                    'port' => $target['port'],
                    'database' => $target['database'],
                    'username' => $target['username'],
                    'password' => $target['password'],
                ],
                'bapps_mysql_configured_at' => now(),
                'config_version' => $agent->config_version + 1,
            ]);

            return $agent->fresh();
        });
    }
}
