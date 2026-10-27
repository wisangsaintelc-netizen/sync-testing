<?php

namespace App\Http\Requests\AgentApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class AgentEventRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'schema_version' => ['required', Rule::in(['1.0'])],
            'event_id' => ['required', 'string', 'max:100'],
            'event_type' => ['required', Rule::in([
                'agent_started', 'heartbeat', 'run_started', 'run_finished', 'sync_error',
                'command_claimed', 'command_completed', 'config_applied', 'outbox_warning',
            ])],
            'agent_code' => ['required', 'string', 'max:100'],
            'run_id' => ['nullable', 'string', 'max:100'],
            'correlation_id' => ['nullable', 'string', 'max:100'],
            'sync_code' => ['nullable', 'string', 'max:100'],
            'occurred_at' => ['required', 'date'],
            'payload' => ['required', 'array'],
        ];
    }
}
