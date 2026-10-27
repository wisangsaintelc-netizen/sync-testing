<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->string('functional_key')->nullable()->after('code');
        });

        foreach ([
            'clientes_valery' => 'co_cli',
            'clientes_profit' => 'co_cli',
            'productos_valery' => 'co_art',
            'productos_profit' => 'co_art',
            'ventas_valery' => 'fact_num',
            'ventas_profit' => 'fact_num',
        ] as $code => $functionalKey) {
            DB::table('sync_catalog')->where('code', $code)->update(['functional_key' => $functionalKey]);
        }

        // Preserve a usable key for any pre-existing custom catalog definition.
        DB::table('sync_catalog')->whereNull('functional_key')->update(['functional_key' => DB::raw('code')]);
    }

    public function down(): void
    {
        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->dropColumn('functional_key');
        });
    }
};
