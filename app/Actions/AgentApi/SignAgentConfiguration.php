<?php

namespace App\Actions\AgentApi;

use JsonException;
use JsonSerializable;
use RuntimeException;

final class SignAgentConfiguration
{
    /** @return array{algorithm: 'ed25519', key_id: string, signature: string}|null */
    public function sign(array $configuration): ?array
    {
        $secretKey = $this->secretKey();

        if ($secretKey === null) {
            return null;
        }

        return [
            'algorithm' => 'ed25519',
            'key_id' => $this->keyId(),
            'signature' => base64_encode(sodium_crypto_sign_detached($this->canonicalJson($configuration), $secretKey)),
        ];
    }

    public function publicKey(): ?string
    {
        $secretKey = $this->secretKey();

        return $secretKey === null
            ? null
            : base64_encode(sodium_crypto_sign_publickey_from_secretkey($secretKey));
    }

    public function keyId(): string
    {
        return (string) config('bapps-sync.recipe_signing_key_id');
    }

    /** @return array{add: list<array{algorithm: 'ed25519', key_id: string, public_key: string}>, retire: list<string>}|null */
    public function trustUpdate(): ?array
    {
        $nextSecretKey = $this->secretKey(
            'bapps-sync.recipe_signing_next_private_key',
            'BAPPS_SYNC_RECIPE_SIGNING_NEXT_PRIVATE_KEY',
        );
        if ($nextSecretKey === null) {
            return null;
        }
        $nextKeyId = (string) config('bapps-sync.recipe_signing_next_key_id');
        if ($nextKeyId === '' || $nextKeyId === $this->keyId()) {
            throw new RuntimeException('La próxima clave de firma requiere un key_id nuevo.');
        }

        return [
            'add' => [[
                'algorithm' => 'ed25519',
                'key_id' => $nextKeyId,
                'public_key' => base64_encode(sodium_crypto_sign_publickey_from_secretkey($nextSecretKey)),
            ]],
            'retire' => [],
        ];
    }

    /** @throws RuntimeException */
    private function secretKey(
        string $configKey = 'bapps-sync.recipe_signing_private_key',
        string $environmentName = 'BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY',
    ): ?string {
        $encoded = config($configKey);

        if ($encoded === null || $encoded === '') {
            return null;
        }
        if (! function_exists('sodium_crypto_sign_detached')) {
            throw new RuntimeException('La extensión Sodium es obligatoria para firmar configuraciones de agentes.');
        }

        $secretKey = base64_decode((string) $encoded, true);
        if ($secretKey === false || strlen($secretKey) !== SODIUM_CRYPTO_SIGN_SECRETKEYBYTES) {
            throw new RuntimeException("{$environmentName} debe ser una clave Ed25519 secreta codificada en base64.");
        }

        return $secretKey;
    }

    private function canonicalJson(array $value): string
    {
        try {
            return json_encode($this->canonicalize($value), JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION);
        } catch (JsonException $exception) {
            throw new RuntimeException('No se pudo serializar la configuración para firma.', previous: $exception);
        }
    }

    private function canonicalize(mixed $value): mixed
    {
        if ($value instanceof JsonSerializable) {
            return $this->canonicalize($value->jsonSerialize());
        }
        if (! is_array($value)) {
            return $value;
        }
        if (array_is_list($value)) {
            return array_map(fn (mixed $item): mixed => $this->canonicalize($item), $value);
        }

        ksort($value, SORT_STRING);

        foreach ($value as $key => $item) {
            $value[$key] = $this->canonicalize($item);
        }

        return $value;
    }
}
