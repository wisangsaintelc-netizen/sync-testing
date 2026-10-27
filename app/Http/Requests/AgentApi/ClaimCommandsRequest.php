<?php

namespace App\Http\Requests\AgentApi;

use Illuminate\Foundation\Http\FormRequest;

class ClaimCommandsRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'agent_code' => ['required', 'string'],
            'max_commands' => ['required', 'integer', 'min:1', 'max:20'],
            'known_command_ids' => ['sometimes', 'array', 'max:100'],
            'known_command_ids.*' => ['string', 'max:100'],
        ];
    }
}
