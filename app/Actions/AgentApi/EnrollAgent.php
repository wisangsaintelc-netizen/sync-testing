<?php

namespace App\Actions\AgentApi;

use App\Models\Agent;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\Hash;
use Illuminate\Validation\ValidationException;

class EnrollAgent
{
    /** @return array{agent_code: string, agent_token: string, config_version: int, config_signing_public_key?: string, config_signing_key_id?: string} */
    public function handle(array $data): array
    {
        $agent = Agent::query()->where('agent_code', $data['agent_code'])->first();

        if ($agent === null || ! $agent->enabled || ! Hash::check($data['enrollment_token'], $agent->credential_hash)) {
            throw ValidationException::withMessages(['enrollment_token' => 'El token de enrolamiento es inválido.']);
        }

        $agentToken = bin2hex(random_bytes(32));
        $agent->update([
            'machine_name' => $data['machine_name'],
            'version' => $data['agent_version'],
            'os' => Arr::get($data, 'os'),
            'status' => 'enrolled',
            'credential_hash' => Hash::make($agentToken),
        ]);

        $response = [
            'agent_code' => $agent->agent_code,
            'agent_token' => $agentToken,
            'config_version' => $agent->config_version,
        ];
        $signer = app(SignAgentConfiguration::class);
        $publicKey = $signer->publicKey();
        if ($publicKey !== null) {
            $response['config_signing_public_key'] = $publicKey;
            $response['config_signing_key_id'] = $signer->keyId();
        }

        return $response;
    }
}
