<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('agents', function (Blueprint $table): void {
            $table->longText('bapps_mysql_config')->nullable()->after('config_version');
            $table->timestamp('bapps_mysql_configured_at')->nullable()->after('bapps_mysql_config');
        });
    }

    public function down(): void
    {
        Schema::table('agents', function (Blueprint $table): void {
            $table->dropColumn(['bapps_mysql_config', 'bapps_mysql_configured_at']);
        });
    }
};
