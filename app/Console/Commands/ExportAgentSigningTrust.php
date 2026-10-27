<?php

namespace App\Console\Commands;

use App\Actions\AgentApi\SignAgentConfiguration;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\File;
use JsonException;

final class ExportAgentSigningTrust extends Command
{
    protected $signature = 'bapps:export-agent-signing-trust
        {output : Ruta del paquete JSON que se incorporará al instalador}';

    protected $description = 'Exporta únicamente la clave pública Ed25519 para un instalador de agentes';

    public function handle(SignAgentConfiguration $signer): int
    {
        $publicKey = $signer->publicKey();
        if ($publicKey === null) {
            $this->components->error('El Centro no tiene configurada la clave privada de firma.');

            return self::FAILURE;
        }

        $path = (string) $this->argument('output');
        File::ensureDirectoryExists(dirname($path));

        try {
            $json = json_encode([
                'schema_version' => '1.0',
                'algorithm' => 'ed25519',
                'key_id' => $signer->keyId(),
                'public_key' => $publicKey,
                'generated_at' => now()->toISOString(),
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        } catch (JsonException) {
            $this->components->error('No se pudo serializar el paquete de confianza.');

            return self::FAILURE;
        }

        File::put($path, $json.PHP_EOL);
        @chmod($path, 0600);
        $this->components->info("Paquete público de confianza generado en {$path}.");

        return self::SUCCESS;
    }
}
