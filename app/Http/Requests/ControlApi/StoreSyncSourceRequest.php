<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;

class StoreSyncSourceRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'system_name' => ['nullable', 'string', 'max:100'],
            'system_version' => ['nullable', 'string', 'max:100'],
            'database_engine' => ['required', 'string', 'max:100'],
            'enabled' => ['sometimes', 'boolean'],
        ];
    }
}
