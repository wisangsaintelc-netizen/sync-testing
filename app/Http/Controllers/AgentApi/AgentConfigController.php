<?php

namespace App\Http\Controllers\AgentApi;

use App\Actions\AgentApi\SignAgentConfiguration;
use App\Http\Controllers\Controller;
use App\Models\Agent;
use Illuminate\Http\JsonResponse;

class AgentConfigController extends Controller
{
    public function __invoke(): JsonResponse
    {
        /** @var Agent $agent */
        $agent = request()->attributes->get('agent');
        $agent->load(['syncs.catalog', 'syncs.recipeVersion']);

        $schemaVersion = version_compare((string) ($agent->version ?? '0.0.0'), '0.2.0', '>=') ? '1.1' : '1.0';
        $configuration = [
            'schema_version' => $schemaVersion,
            'version' => $agent->config_version,
            'agent_code' => $agent->agent_code,
            'syncs' => $agent->syncs->map(fn ($assignment): array => [
                'code' => $assignment->catalog->code,
                // The assignment keeps its own state. A globally disabled catalog
                // is projected as disabled so the agent cannot schedule it.
                'status' => $assignment->catalog->enabled_globally ? $assignment->status : 'disabled',
                'interval_seconds' => $assignment->interval_seconds,
                'config' => $assignment->recipeVersion === null
                    ? ($assignment->config_json ?? [])
                    : [
                        'recipe' => $assignment->recipeVersion->payload_json,
                        ...($assignment->config_json === null ? [] : ['assignment' => $assignment->config_json]),
                        ...($assignment->secret_config === null ? [] : ['secrets' => $assignment->secret_config]),
                    ],
            ])->values()->all(),
        ];

        if ($schemaVersion === '1.1' && $agent->bapps_mysql_config !== null) {
            $configuration['targets'] = [
                'bapps_mysql' => [
                    ...$agent->bapps_mysql_config,
                    'configured_at' => $agent->bapps_mysql_configured_at?->toISOString(),
                ],
            ];
        }

        $signer = app(SignAgentConfiguration::class);
        if ($trustUpdate = $signer->trustUpdate()) {
            $configuration['config_signing_trust_update'] = $trustUpdate;
        }
        if ($signature = $signer->sign($configuration)) {
            $configuration['config_signature'] = $signature;
        }

        return response()->json($configuration);
    }
}
