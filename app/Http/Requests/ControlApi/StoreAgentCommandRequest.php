<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreAgentCommandRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'type' => ['required', Rule::in(['run_now', 'stop_run', 'pause_sync', 'resume_sync', 'refresh_config', 'inspect_source_table'])],
            'sync_code' => ['nullable', 'string', 'max:100', 'required_if:type,run_now,pause_sync,resume_sync'],
            'run_id' => ['nullable', 'string', 'max:100', 'required_if:type,stop_run'],
            'profile_ref' => ['nullable', 'string', 'max:64', 'regex:/^[A-Za-z_][A-Za-z0-9_-]{0,63}$/', 'required_if:type,inspect_source_table'],
            'driver' => ['nullable', Rule::in(['firebird', 'sqlserver']), 'required_if:type,inspect_source_table'],
            'schema' => ['nullable', 'string', 'max:63', 'regex:/^[A-Za-z_][A-Za-z0-9_$]{0,62}$/'],
            'table' => ['nullable', 'string', 'max:63', 'regex:/^[A-Za-z_][A-Za-z0-9_$]{0,62}$/', 'required_if:type,inspect_source_table'],
            'position' => ['nullable', 'integer', 'min:1', 'max:10000', 'required_if:type,inspect_source_table'],
        ];
    }
}
