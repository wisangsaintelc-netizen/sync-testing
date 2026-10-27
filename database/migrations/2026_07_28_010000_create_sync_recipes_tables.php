<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sync_recipes', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('sync_catalog_id')->unique()->constrained('sync_catalog')->cascadeOnDelete();
            $table->timestamps();
        });

        Schema::create('sync_recipe_versions', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('sync_recipe_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('version');
            $table->json('payload_json');
            $table->string('payload_hash', 71);
            $table->foreignId('published_by')->nullable()->constrained('users')->nullOnDelete();
            $table->dateTime('published_at');
            $table->timestamps();

            $table->unique(['sync_recipe_id', 'version']);
            $table->index(['sync_recipe_id', 'published_at']);
        });

        Schema::table('agent_syncs', function (Blueprint $table): void {
            $table->foreignId('sync_recipe_version_id')->nullable()->after('sync_catalog_id')
                ->constrained('sync_recipe_versions')->nullOnDelete();
        });
    }

    public function down(): void
    {
        Schema::table('agent_syncs', function (Blueprint $table): void {
            $table->dropConstrainedForeignId('sync_recipe_version_id');
        });
        Schema::dropIfExists('sync_recipe_versions');
        Schema::dropIfExists('sync_recipes');
    }
};
