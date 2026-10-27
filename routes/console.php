<?php

use App\Actions\ControlApi\ConfigureAgentBappsMysql;
use App\Actions\ControlApi\QueueAgentRun;
use App\Models\Agent;
use App\Models\AgentSync;
use App\Models\Client;
use App\Models\SyncCatalog;
use App\Models\SyncCommand;
use App\Models\SyncRun;
use App\Models\User;
use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\File;
use Illuminate\Support\Facades\Hash;
use Illuminate\Support\Facades\Schedule;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Str;

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');

Schedule::call(static function (): void {
    SyncCommand::query()
        ->where('command_type', 'inspect_source_table')
        ->where('expires_at', '<=', now())
        ->whereNotNull('result_json')
        ->update(['result_json' => null]);
})->everyFiveMinutes()->name('purge-source-inspection-previews')->withoutOverlapping();

Artisan::command('bapps:configure-mysql-target
    {agent-code : Código del agente que recibirá el destino}
    {--host= : Host o IP del MySQL BAPPS}
    {--port=3306 : Puerto MySQL}
    {--database= : Base de datos BAPPS}
    {--username= : Usuario MySQL BAPPS}', function (ConfigureAgentBappsMysql $configure): int {
    $agent = Agent::query()->where('agent_code', (string) $this->argument('agent-code'))->first();
    if ($agent === null) {
        $this->error('No existe el agente indicado.');

        return self::FAILURE;
    }

    $target = [
        'host' => (string) ($this->option('host') ?: $this->ask('Host o IP MySQL BAPPS')),
        'port' => (int) $this->option('port'),
        'database' => (string) ($this->option('database') ?: $this->ask('Base de datos BAPPS')),
        'username' => (string) ($this->option('username') ?: $this->ask('Usuario MySQL BAPPS')),
        'password' => (string) $this->secret('Contraseña MySQL BAPPS'),
    ];

    if ($target['host'] === '' || $target['database'] === '' || $target['username'] === '' || $target['password'] === '') {
        $this->error('Host, base, usuario y contraseña son obligatorios.');

        return self::FAILURE;
    }
    if ($target['port'] < 1 || $target['port'] > 65535) {
        $this->error('El puerto debe estar entre 1 y 65535.');

        return self::FAILURE;
    }

    $configured = $configure->handle($agent, $target);
    $this->info("Destino MySQL BAPPS publicado para {$configured->agent_code}, configuración v{$configured->config_version}.");
    $this->line('La contraseña fue cifrada en el Centro BAPPS y no se muestra en consola.');

    return self::SUCCESS;
})->purpose('Publica el destino MySQL BAPPS cifrado para un agente');

Artisan::command('bapps:queue-run
    {agent-code : Código del agente}
    {sync-code=clientes_valery : Código del sincronizador habilitado}', function (QueueAgentRun $queueRun): int {
    $agent = Agent::query()->where('agent_code', (string) $this->argument('agent-code'))->first();
    if ($agent === null) {
        $this->error('No existe el agente indicado.');

        return self::FAILURE;
    }

    try {
        $command = $queueRun->handle($agent, (string) $this->argument('sync-code'));
    } catch (RuntimeException $exception) {
        $this->error($exception->getMessage());

        return self::FAILURE;
    }

    $this->info("Comando {$command->command_id} publicado para {$agent->agent_code}.");

    return self::SUCCESS;
})->purpose('Solicita una ejecución manual de un sincronizador en un agente');

Artisan::command('bapps:create-retry-test-run
    {agent-code : Código del agente que ejecutará el reintento}
    {sync-code=clientes_valery : Código del sincronizador habilitado}', function (): int {
    $agent = Agent::query()->where('agent_code', (string) $this->argument('agent-code'))->first();
    if ($agent === null || ! $agent->enabled) {
        $this->error('El agente no existe o está deshabilitado.');

        return self::FAILURE;
    }

    $syncCode = (string) $this->argument('sync-code');
    $assignment = AgentSync::query()
        ->with('catalog')
        ->where('agent_id', $agent->id)
        ->where('status', 'enabled')
        ->whereHas('catalog', fn ($catalog) => $catalog->where('code', $syncCode)->where('enabled_globally', true))
        ->first();

    if ($assignment === null) {
        $this->error("{$syncCode} no está habilitado para {$agent->agent_code}.");

        return self::FAILURE;
    }

    $run = SyncRun::query()->create([
        'run_id' => 'RUN-RETRY-TEST-'.Str::lower((string) Str::uuid()),
        'agent_id' => $agent->id,
        'client_id' => $agent->client_id,
        'sync_catalog_id' => $assignment->sync_catalog_id,
        'status' => 'failed',
        'trigger' => 'manual',
        'started_at' => now()->subSecond(),
        'finished_at' => now(),
        'duration_ms' => 1000,
        // Use a catalogued retryable code so the real UI exposes the retry
        // control while the technical message makes the synthetic nature clear.
        'error_code' => 'TARGET_CONNECTION_FAILED',
        'error_message' => 'Ejecución sintética para validar el reintento seguro; no se ejecutó ningún sincronizador.',
        'agent_version' => $agent->version,
    ]);

    $this->info("Ejecución sintética {$run->run_id} creada para {$agent->agent_code}.");
    $this->warn('No se tocó Firebird, MySQL BAPPS ni la configuración del agente. Abra esta ejecución y pulse Reintentar ejecución.');

    return self::SUCCESS;
})->purpose('Crea una ejecución fallida sintética para probar el reintento seguro sin alterar datos de negocio');

Artisan::command('bapps:demo-provision
    {--agent-code=AGT-DEMO : Código del agente de demostración}
    {--enrollment-token=demo-enrollment-token-123456 : Credencial de enrolamiento (solo desarrollo)}
    {--bootstrap-output= : Ruta de bootstrap.json para el portable}
    {--base-url= : URL alcanzable del Centro BAPPS para el portable}
    {--with-command : Publica un comando run_now pendiente para probar el sondeo}', function (): int {
    $agentCode = (string) $this->option('agent-code');
    $enrollmentToken = (string) $this->option('enrollment-token');

    if (mb_strlen($enrollmentToken) < 16) {
        $this->error('El token de enrolamiento debe tener al menos 16 caracteres.');

        return self::FAILURE;
    }

    $operator = User::query()->updateOrCreate(
        ['email' => 'operator@bapps.test'],
        ['name' => 'Operador de demostración', 'password' => 'bapps-demo-password'],
    );

    $client = Client::query()->updateOrCreate(
        ['name' => 'Cliente de demostración BAPPS'],
        ['system_type' => 'BAPPS', 'status' => 'active', 'timezone' => 'America/Caracas'],
    );

    $catalog = SyncCatalog::query()->updateOrCreate(
        ['code' => 'clientes_valery'],
        [
            'name' => 'Clientes Valery',
            'source_type' => 'firebird',
            'min_agent_version' => '0.3.0',
            'enabled_globally' => true,
            'default_interval_seconds' => 900,
            'description' => 'Sincronización de prueba para clientes Valery.',
        ],
    );

    $agent = Agent::query()->updateOrCreate(
        ['agent_code' => $agentCode],
        [
            'client_id' => $client->id,
            'status' => 'pending_enrollment',
            'enabled' => true,
            'credential_hash' => Hash::make($enrollmentToken),
            'config_version' => 1,
        ],
    );

    AgentSync::query()->updateOrCreate(
        ['agent_id' => $agent->id, 'sync_catalog_id' => $catalog->id],
        [
            'status' => 'enabled',
            'interval_seconds' => 900,
            'config_version' => 1,
            'config_json' => ['batch_size' => 200],
        ],
    );

    if ($this->option('with-command')) {
        SyncCommand::query()->updateOrCreate(
            ['command_id' => 'CMD-DEMO-RUN-NOW'],
            [
                'agent_id' => $agent->id,
                'command_type' => 'run_now',
                'sync_code' => $catalog->code,
                'payload_json' => ['sync_code' => $catalog->code],
                'status' => 'pending',
                'idempotency_key' => 'demo-run-now-'.$agentCode,
                'created_by' => $operator->id,
                'issued_at' => now(),
                'expires_at' => now()->addHour(),
                'claimed_at' => null,
                'lease_expires_at' => null,
                'completed_at' => null,
                'result_json' => null,
            ],
        );
    }

    if ($bootstrapOutput = $this->option('bootstrap-output')) {
        $bootstrapPath = (string) $bootstrapOutput;
        $bootstrapDirectory = dirname($bootstrapPath);
        if (! File::isDirectory($bootstrapDirectory)) {
            File::makeDirectory($bootstrapDirectory, 0755, true);
        }
        $baseUrl = rtrim((string) ($this->option('base-url') ?: config('app.url')), '/');
        File::put($bootstrapPath, json_encode([
            'schema_version' => '1.0',
            'base_url' => $baseUrl,
            'agent_code' => $agent->agent_code,
            'enrollment_token' => $enrollmentToken,
            'issued_at' => now()->toISOString(),
        ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES).PHP_EOL);
    }

    $this->newLine();
    $this->info('Entorno de demostración preparado.');
    $this->table(['Dato', 'Valor'], [
        ['Operador', 'operator@bapps.test / bapps-demo-password'],
        ['Cliente', $client->name],
        ['Agente', $agent->agent_code],
        ['Token de enrolamiento', $enrollmentToken],
        ['Sincronización', $catalog->code.' (cada 900 s)'],
        ['Comando pendiente', $this->option('with-command') ? 'CMD-DEMO-RUN-NOW' : 'No solicitado'],
        ['Bootstrap', $this->option('bootstrap-output') ?: 'No solicitado'],
    ]);
    $this->warn('Solo para desarrollo: al volver a ejecutar el comando se restablece la credencial de enrolamiento.');

    return self::SUCCESS;
})->purpose('Prepara datos reproducibles para probar BAPPS Sync en desarrollo');

Artisan::command('bapps:copy-central-sqlite-to-mysql
    {--source= : Ruta de la SQLite central histórica; por defecto database/database.sqlite}', function (): int {
    $sourcePath = (string) ($this->option('source') ?: database_path('database.sqlite'));
    if (! is_file($sourcePath)) {
        $this->error("No existe la SQLite de origen: {$sourcePath}");

        return self::FAILURE;
    }

    $tables = [
        'users' => 'id',
        'password_reset_tokens' => 'email',
        'clients' => 'id',
        'sync_catalog' => 'id',
        'agents' => 'id',
        'agent_syncs' => 'id',
        'sync_commands' => 'id',
        'sync_runs' => 'id',
        'sync_events' => 'id',
        'sync_audit_events' => 'id',
        'personal_access_tokens' => 'id',
    ];

    $legacyConnection = array_replace(config('database.connections.sqlite'), ['database' => $sourcePath]);
    config(['database.connections.sqlite_legacy' => $legacyConnection]);
    DB::purge('sqlite_legacy');
    $source = DB::connection('sqlite_legacy');
    $target = DB::connection('mysql');

    foreach (array_keys($tables) as $table) {
        if (! Schema::connection('mysql')->hasTable($table)) {
            $this->error("Falta la tabla {$table} en MySQL. Ejecute primero php artisan migrate --force.");

            return self::FAILURE;
        }
        if (Schema::connection('sqlite_legacy')->hasTable($table) && $target->table($table)->exists()) {
            $this->error("MySQL ya contiene datos en {$table}. La transferencia se cancela para no sobrescribir ni duplicar datos.");

            return self::FAILURE;
        }
    }

    $copied = [];
    $target->transaction(function () use (&$copied, $source, $tables, $target): void {
        foreach ($tables as $table => $orderBy) {
            if (! Schema::connection('sqlite_legacy')->hasTable($table)) {
                continue;
            }

            $batch = [];
            $count = 0;
            foreach ($source->table($table)->orderBy($orderBy)->cursor() as $row) {
                $batch[] = (array) $row;
                if (count($batch) === 500) {
                    $target->table($table)->insert($batch);
                    $count += count($batch);
                    $batch = [];
                }
            }
            if ($batch !== []) {
                $target->table($table)->insert($batch);
                $count += count($batch);
            }
            $copied[$table] = $count;
        }
    });

    $this->info('Transferencia SQLite -> MySQL completada.');
    foreach ($copied as $table => $count) {
        $this->line("{$table}: {$count}");
    }

    return self::SUCCESS;
})->purpose('Copia de forma segura los datos operativos de la SQLite central histórica a MySQL vacío');
