<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateAgentSyncRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'status' => ['sometimes', Rule::in(['enabled', 'paused', 'disabled'])],
            'interval_seconds' => ['sometimes', 'integer', 'min:60', 'max:86400'],
            'sync_recipe_version_id' => ['sometimes', 'integer', 'exists:sync_recipe_versions,id'],
        ];
    }
}
