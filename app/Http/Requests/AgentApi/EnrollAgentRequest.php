<?php

namespace App\Http\Requests\AgentApi;

use Illuminate\Foundation\Http\FormRequest;

class EnrollAgentRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'agent_code' => ['required', 'string', 'max:100'],
            'enrollment_token' => ['required', 'string', 'min:16', 'max:512'],
            'machine_name' => ['required', 'string', 'max:255'],
            'agent_version' => ['required', 'string', 'max:100'],
            'os' => ['nullable', 'string', 'max:100'],
        ];
    }
}
