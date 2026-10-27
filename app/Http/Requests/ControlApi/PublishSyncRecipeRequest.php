<?php

namespace App\Http\Requests\ControlApi;

use App\Support\ReadRecipeValidationRules;
use Illuminate\Foundation\Http\FormRequest;

class PublishSyncRecipeRequest extends FormRequest
{
    public function authorize(): bool
    {
        return $this->user() !== null;
    }

    public function rules(): array
    {
        return ReadRecipeValidationRules::rules();
    }

    public function recipe(): array
    {
        return $this->validated('recipe');
    }
}
