<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sync_sources', function (Blueprint $table): void {
            $table->id();
            $table->string('system_name')->nullable();
            $table->string('system_version')->nullable();
            $table->string('database_engine');
            $table->boolean('enabled')->default(true);
            $table->timestamps();

            $table->index(['system_name', 'system_version', 'database_engine']);
        });

        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->foreignId('sync_source_id')->nullable()->after('functional_key')
                ->constrained('sync_sources')->nullOnDelete();
        });

        DB::table('sync_catalog')->orderBy('id')->each(function (object $catalog): void {
            $source = $this->sourceForLegacyType((string) $catalog->source_type);
            $sourceId = DB::table('sync_sources')
                ->where('system_name', $source['system_name'])
                ->whereNull('system_version')
                ->where('database_engine', $source['database_engine'])
                ->value('id');

            if ($sourceId === null) {
                $sourceId = DB::table('sync_sources')->insertGetId([
                    ...$source,
                    'created_at' => now(),
                    'updated_at' => now(),
                ]);
            }

            DB::table('sync_catalog')->where('id', $catalog->id)->update(['sync_source_id' => $sourceId]);
        });
    }

    public function down(): void
    {
        Schema::table('sync_catalog', function (Blueprint $table): void {
            $table->dropConstrainedForeignId('sync_source_id');
        });

        Schema::dropIfExists('sync_sources');
    }

    /** @return array{system_name: ?string, system_version: ?string, database_engine: string, enabled: bool} */
    private function sourceForLegacyType(string $source): array
    {
        if (! str_contains($source, '/')) {
            return [
                'system_name' => null,
                'system_version' => null,
                'database_engine' => $this->databaseLabel($source),
                'enabled' => true,
            ];
        }

        [$system, $database] = array_pad(array_map('trim', explode('/', $source, 2)), 2, null);

        return [
            'system_name' => $system ?: 'Origen heredado',
            'system_version' => null,
            'database_engine' => $this->databaseLabel($database ?: ($system ?: 'Desconocida')),
            'enabled' => true,
        ];
    }

    private function databaseLabel(string $database): string
    {
        return match (strtolower($database)) {
            'firebird' => 'Firebird',
            'mysql' => 'MySQL',
            'sql server' => 'SQL Server',
            default => $database,
        };
    }
};
