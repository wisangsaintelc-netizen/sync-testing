<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('sync_runs', function (Blueprint $table): void {
            $table->foreignId('reviewed_by')->nullable()->constrained('users')->nullOnDelete();
            $table->dateTime('reviewed_at')->nullable();
            $table->index(['client_id', 'status', 'reviewed_at', 'started_at']);
        });
    }

    public function down(): void
    {
        Schema::table('sync_runs', function (Blueprint $table): void {
            $table->dropIndex(['client_id', 'status', 'reviewed_at', 'started_at']);
            $table->dropConstrainedForeignId('reviewed_by');
            $table->dropColumn('reviewed_at');
        });
    }
};
