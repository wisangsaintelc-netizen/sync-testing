<?php

namespace App\Http\Requests\AgentApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class HeartbeatRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'schema_version' => ['required', Rule::in(['1.0'])],
            'agent_code' => ['required', 'string', 'max:100'],
            'agent_version' => ['required', 'string', 'max:100'],
            'config_version' => ['required', 'integer', 'min:0'],
            'machine_name' => ['required', 'string', 'max:255'],
            'status' => ['required', Rule::in(['online'])],
            'running_runs' => ['present', 'array', 'max:50'],
            'running_runs.*.run_id' => ['required', 'string', 'max:100'],
            'running_runs.*.sync_code' => ['required', 'string', 'max:100'],
            'running_runs.*.status' => ['required', Rule::in(['running', 'stopping'])],
            'running_runs.*.started_at' => ['required', 'date'],
            'outbox' => ['required', 'array'],
            'outbox.pending_count' => ['required', 'integer', 'min:0'],
            'outbox.pending_bytes' => ['required', 'integer', 'min:0'],
        ];
    }
}
