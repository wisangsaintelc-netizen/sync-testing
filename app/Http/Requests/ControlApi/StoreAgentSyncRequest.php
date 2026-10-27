<?php

namespace App\Http\Requests\ControlApi;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;

class StoreAgentSyncRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'sync_code' => ['required', 'string', 'max:100', 'regex:/^[a-z][a-z0-9_]{1,99}$/'],
            'status' => ['required', Rule::in(['enabled', 'paused', 'disabled'])],
            'interval_seconds' => ['required', 'integer', 'min:60', 'max:86400'],
            'config' => ['sometimes', 'array:profile_ref,warehouse_code,station_code,user_code,server_code,orders_api_url'],
            'config.profile_ref' => ['required_with:config', 'string', 'max:64', 'regex:/^[A-Za-z_][A-Za-z0-9_-]*$/'],
            'config.warehouse_code' => ['required_with:config', 'string', 'max:15'],
            'config.station_code' => ['required_with:config', 'string', 'max:15'],
            'config.user_code' => ['required_with:config', 'string', 'max:15'],
            'config.server_code' => ['required_with:config', 'string', 'max:15'],
            'config.orders_api_url' => ['required_with:config', 'url:http,https', 'max:2048'],
            'secrets' => ['sometimes', 'array:orders_api_token'],
            'secrets.orders_api_token' => ['required_with:secrets', 'string', 'min:32', 'max:4096'],
        ];
    }
}
