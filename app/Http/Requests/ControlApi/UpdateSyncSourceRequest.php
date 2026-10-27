<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;

class UpdateSyncSourceRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'system_name' => ['sometimes', 'nullable', 'string', 'max:100'],
            'system_version' => ['sometimes', 'nullable', 'string', 'max:100'],
            'database_engine' => ['sometimes', 'string', 'max:100'],
            'enabled' => ['sometimes', 'boolean'],
        ];
    }
}
