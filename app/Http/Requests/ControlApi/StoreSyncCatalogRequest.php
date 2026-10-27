<?php

namespace App\Http\Requests\ControlApi;

use App\Support\ReadRecipeValidationRules;
use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

class StoreSyncCatalogRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        $rules = [
            'code' => ['required', 'string', 'max:100', 'regex:/^[a-z][a-z0-9_]*$/', Rule::unique('sync_catalog', 'code')],
            'functional_key' => ['required', 'string', 'max:100', 'regex:/^[A-Za-z][A-Za-z0-9_]*$/'],
            'direction' => ['required', Rule::in(['read', 'write'])],
            'name' => ['required', 'string', 'max:150'],
            'source_id' => [
                'required',
                'integer',
                Rule::exists('sync_sources', 'id')->where('enabled', true),
            ],
            'min_agent_version' => ['required', 'string', 'max:50'],
            'enabled_globally' => ['sometimes', 'boolean'],
            'default_interval_seconds' => ['required', 'integer', 'min:60', 'max:86400'],
            'description' => ['nullable', 'string', 'max:2000'],
        ];

        return $this->has('recipe')
            ? [...$rules, ...ReadRecipeValidationRules::rules()]
            : $rules;
    }

    /** @return array<int, callable> */
    public function after(): array
    {
        return [
            function (Validator $validator): void {
                $recipe = $this->input('recipe');
                if (! is_array($recipe)) {
                    return;
                }
                if (($recipe['recipe_code'] ?? null) !== $this->input('code')) {
                    $validator->errors()->add('recipe.recipe_code', 'El código de la receta debe coincidir con el código del sincronizador.');
                }
                if (($recipe['minimum_agent_version'] ?? null) !== $this->input('min_version')) {
                    $validator->errors()->add('recipe.minimum_agent_version', 'La versión mínima de la receta debe coincidir con la del sincronizador.');
                }
                $recipeDirection = $recipe['direction'] ?? 'read';
                if ($recipeDirection !== $this->input('direction')) {
                    $validator->errors()->add('recipe.direction', 'La dirección de la receta debe coincidir con la del sincronizador.');
                }
            },
        ];
    }

    protected function prepareForValidation(): void
    {
        $code = $this->input('code');
        $this->merge([
            'code' => is_string($code) ? Str::lower(trim($code)) : $code,
            'functional_key' => $this->input('key'),
            'direction' => $this->input('direction', 'read'),
            'min_agent_version' => $this->input('min_version'),
            'enabled_globally' => $this->has('enabled') ? $this->input('enabled') : true,
            'default_interval_seconds' => $this->input('interval_seconds'),
            'description' => $this->input('desc'),
        ]);
    }
}
