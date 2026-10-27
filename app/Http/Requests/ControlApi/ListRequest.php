<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class ListRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'page' => ['nullable', 'integer', 'min:1'],
            'page_size' => ['nullable', 'integer', 'min:1', 'max:100'],
            'status' => ['nullable', 'string', 'max:32'],
            'search' => ['nullable', 'string', 'max:100'],
            'kind' => ['nullable', Rule::in(['command', 'event', 'error', 'config', 'auth'])],
            'health' => ['nullable', Rule::in(['ok', 'warning', 'error', 'enrolled'])],
        ];
    }

    public function pageSize(): int
    {
        return (int) ($this->validated('page_size') ?? 25);
    }
}
