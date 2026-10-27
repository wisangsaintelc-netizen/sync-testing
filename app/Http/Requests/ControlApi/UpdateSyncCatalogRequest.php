<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class UpdateSyncCatalogRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'code' => ['prohibited'],
            'direction' => ['prohibited'],
            'key' => ['sometimes', 'string', 'max:100', 'regex:/^[A-Za-z][A-Za-z0-9_]*$/'],
            'name' => ['sometimes', 'string', 'max:150'],
            'source_id' => [
                'sometimes',
                'integer',
                Rule::exists('sync_sources', 'id')->where('enabled', true),
            ],
            'min_version' => ['sometimes', 'string', 'max:50'],
            'enabled' => ['sometimes', 'boolean'],
            'desc' => ['sometimes', 'nullable', 'string', 'max:2000'],
            'interval_seconds' => ['sometimes', 'integer', 'min:60', 'max:86400'],
        ];
    }

    public function catalogData(): array
    {
        $validated = parent::validated();
        $mapping = [
            'functional_key' => 'key',
            'sync_source_id' => 'source_id',
            'min_agent_version' => 'min_version',
            'enabled_globally' => 'enabled',
            'description' => 'desc',
            'default_interval_seconds' => 'interval_seconds',
        ];

        foreach ($mapping as $target => $source) {
            if (array_key_exists($source, $validated)) {
                $validated[$target] = $validated[$source];
                unset($validated[$source]);
            }
        }

        return $validated;
    }
}
