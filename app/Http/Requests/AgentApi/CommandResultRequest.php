<?php

namespace App\Http\Requests\AgentApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

class CommandResultRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'status' => ['required', Rule::in(['completed', 'failed', 'skipped'])],
            'completed_at' => ['required', 'date'],
            'result' => ['nullable', 'array'],
        ];
    }

    /** @return array<int, callable(Validator): void> */
    public function after(): array
    {
        return [
            function (Validator $validator): void {
                $result = $this->input('result');
                if (! is_array($result)) {
                    return;
                }
                $encoded = json_encode($result);
                if (! is_string($encoded) || strlen($encoded) > 262_144) {
                    $validator->errors()->add('result', 'El resultado del comando excede el límite permitido.');

                    return;
                }
                $columns = $result['columns'] ?? null;
                $position = $result['position'] ?? null;
                if ($position !== null && (! is_int($position) || $position < 1 || $position > 10_000)) {
                    $validator->errors()->add('result.position', 'La posición de inspección no es válida.');
                }
                foreach (['has_row', 'has_next'] as $key) {
                    if (array_key_exists($key, $result) && ! is_bool($result[$key])) {
                        $validator->errors()->add("result.{$key}", 'El indicador de inspección no es válido.');
                    }
                }
                if ($columns === null) {
                    return;
                }
                if (! is_array($columns) || count($columns) > 256) {
                    $validator->errors()->add('result.columns', 'La inspección excede el límite de 256 columnas.');

                    return;
                }
                foreach ($columns as $index => $column) {
                    if (
                        ! is_array($column)
                        || ! is_string($column['name'] ?? null)
                        || strlen($column['name']) > 128
                        || ! is_string($column['type'] ?? null)
                        || strlen($column['type']) > 128
                        || (isset($column['sample']) && ! is_scalar($column['sample']))
                    ) {
                        $validator->errors()->add("result.columns.{$index}", 'La columna inspeccionada no tiene un formato válido.');
                    }
                }
            },
        ];
    }
}
