<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->string('direction', 16)->default('read')->after('functional_key')->index();
        });

        Schema::table('agent_syncs', function (Blueprint $table): void {
            $table->longText('secret_config')->nullable()->after('config_json');
        });
    }

    public function down(): void
    {
        Schema::table('agent_syncs', function (Blueprint $table): void {
            $table->dropColumn('secret_config');
        });

        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->dropIndex(['direction']);
            $table->dropColumn('direction');
        });
    }
};
