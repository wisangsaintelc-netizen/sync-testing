<?php

return [
    'agent_header' => env('BAPPS_SYNC_AGENT_HEADER', 'X-Agent-Code'),
    'agent_max_request_bytes' => (int) env('BAPPS_SYNC_AGENT_MAX_REQUEST_BYTES', 65_536),
    'agent_online_threshold_seconds' => (int) env('BAPPS_SYNC_AGENT_ONLINE_THRESHOLD_SECONDS', 120),
    'command_lease_seconds' => (int) env('BAPPS_SYNC_COMMAND_LEASE_SECONDS', 120),
    'command_claim_limit' => (int) env('BAPPS_SYNC_COMMAND_CLAIM_LIMIT', 5),
    // Base64-encoded Ed25519 secret key. Keep it outside the database and
    // provide it only to the server that signs agent configuration.
    'recipe_signing_private_key' => env('BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY'),
    'recipe_signing_key_id' => env('BAPPS_SYNC_RECIPE_SIGNING_KEY_ID', 'recipe-v1'),
    // Optional planned rotation. The active key signs the introduction of the
    // next public key before the Center switches signers.
    'recipe_signing_next_private_key' => env('BAPPS_SYNC_RECIPE_SIGNING_NEXT_PRIVATE_KEY'),
    'recipe_signing_next_key_id' => env('BAPPS_SYNC_RECIPE_SIGNING_NEXT_KEY_ID'),
];
