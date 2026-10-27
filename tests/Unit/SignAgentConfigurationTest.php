<?php

namespace Tests\Unit;

use App\Actions\AgentApi\SignAgentConfiguration;
use Illuminate\Support\Collection;
use RuntimeException;
use Tests\TestCase;

final class SignAgentConfigurationTest extends TestCase
{
    public function test_signature_survives_the_json_response_round_trip_with_nested_collections(): void
    {
        $secret = sodium_crypto_sign_secretkey(sodium_crypto_sign_keypair());
        config()->set('bapps-sync.recipe_signing_private_key', base64_encode($secret));
        config()->set('bapps-sync.recipe_signing_key_id', 'recipe-v1');
        $configuration = [
            'schema_version' => '1.1',
            'agent_code' => 'AGT-VALERY-01',
            'syncs' => new Collection([[
                'code' => 'clientes_valery',
                'status' => 'enabled',
                'interval_seconds' => 60,
                'config' => [],
            ]]),
        ];

        $signature = app(SignAgentConfiguration::class)->sign($configuration);
        $wireConfiguration = json_decode(
            response()->json([...$configuration, 'config_signature' => $signature])->getContent(),
            true,
            512,
            JSON_THROW_ON_ERROR,
        );
        $wireSignature = base64_decode($wireConfiguration['config_signature']['signature'], true);
        unset($wireConfiguration['config_signature']);

        $canonicalize = function (mixed $value) use (&$canonicalize): mixed {
            if (! is_array($value)) {
                return $value;
            }
            if (array_is_list($value)) {
                return array_map(fn (mixed $item): mixed => $canonicalize($item), $value);
            }
            ksort($value, SORT_STRING);
            foreach ($value as $key => $item) {
                $value[$key] = $canonicalize($item);
            }

            return $value;
        };
        $wireJson = json_encode(
            $canonicalize($wireConfiguration),
            JSON_THROW_ON_ERROR | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRESERVE_ZERO_FRACTION,
        );

        $this->assertTrue(sodium_crypto_sign_verify_detached(
            $wireSignature,
            $wireJson,
            sodium_crypto_sign_publickey_from_secretkey($secret),
        ));
    }

    public function test_active_key_introduces_a_distinct_next_public_key(): void
    {
        $active = sodium_crypto_sign_secretkey(sodium_crypto_sign_keypair());
        $next = sodium_crypto_sign_secretkey(sodium_crypto_sign_keypair());
        config()->set('bapps-sync.recipe_signing_private_key', base64_encode($active));
        config()->set('bapps-sync.recipe_signing_key_id', 'recipe-v1');
        config()->set('bapps-sync.recipe_signing_next_private_key', base64_encode($next));
        config()->set('bapps-sync.recipe_signing_next_key_id', 'recipe-v2');

        $update = app(SignAgentConfiguration::class)->trustUpdate();

        $this->assertSame('recipe-v2', $update['add'][0]['key_id']);
        $this->assertSame(
            sodium_crypto_sign_publickey_from_secretkey($next),
            base64_decode($update['add'][0]['public_key'], true),
        );
        $this->assertSame([], $update['retire']);
    }

    public function test_rotation_rejects_reusing_the_active_key_id(): void
    {
        $key = sodium_crypto_sign_secretkey(sodium_crypto_sign_keypair());
        config()->set('bapps-sync.recipe_signing_private_key', base64_encode($key));
        config()->set('bapps-sync.recipe_signing_key_id', 'recipe-v1');
        config()->set('bapps-sync.recipe_signing_next_private_key', base64_encode($key));
        config()->set('bapps-sync.recipe_signing_next_key_id', 'recipe-v1');

        $this->expectException(RuntimeException::class);
        app(SignAgentConfiguration::class)->trustUpdate();
    }
}
