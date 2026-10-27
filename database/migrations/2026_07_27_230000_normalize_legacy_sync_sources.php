<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        foreach (['firebird' => 'Firebird', 'mysql' => 'MySQL', 'sql server' => 'SQL Server'] as $legacy => $label) {
            DB::table('sync_sources')
                ->whereRaw('LOWER(system_name) = ?', [$legacy])
                ->whereRaw('LOWER(database_engine) = ?', [$legacy])
                ->update(['system_name' => null, 'database_engine' => $label, 'updated_at' => now()]);
        }
    }

    public function down(): void
    {
        // The old duplicate label is intentionally not restored.
    }
};
