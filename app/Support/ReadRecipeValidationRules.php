<?php

namespace App\Support;

final class ReadRecipeValidationRules
{
    /** @return array<string, array<int, mixed>> */
    public static function rules(): array
    {
        if (request()->input('recipe.engine') === 'valery_prs_writer_v1') {
            return self::writerRules();
        }

        return [
            'recipe' => ['required', 'array:schema_version,recipe_code,recipe_version,engine,minimum_agent_version,source,scope,target,constants,transformations,limits'],
            'recipe.schema_version' => ['required', 'in:1.0'],
            'recipe.recipe_code' => ['required', 'string', 'max:128', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/'],
            'recipe.recipe_version' => ['prohibited'],
            'recipe.engine' => ['required', 'in:declarative_table_reader'],
            'recipe.minimum_agent_version' => ['required', 'regex:/^\d+\.\d+\.\d+$/'],
            'recipe.source' => ['required', 'array:profile_ref,driver,schema,table,columns,schema_fingerprint'],
            'recipe.source.profile_ref' => ['required', 'string', 'max:64', 'regex:/^[A-Za-z_][A-Za-z0-9_-]*$/'],
            'recipe.source.driver' => ['required', 'in:sqlserver,firebird'],
            'recipe.source.schema' => [
                'required_if:recipe.source.driver,sqlserver',
                'prohibited_if:recipe.source.driver,firebird',
                'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/',
            ],
            'recipe.source.table' => ['required', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/'],
            'recipe.source.columns' => ['required', 'array', 'min:1', 'max:512'],
            'recipe.source.columns.*' => ['string', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/', 'distinct'],
            'recipe.source.schema_fingerprint' => ['sometimes', 'string', 'regex:/^sha256:[a-f0-9]{64}$/'],
            'recipe.scope' => ['sometimes', 'array:where'],
            'recipe.scope.where' => ['required_with:recipe.scope', 'array:operator,column,window,value,values'],
            'recipe.scope.where.operator' => ['required_with:recipe.scope.where', 'in:eq,in,is_null,is_not_null,date_window'],
            'recipe.scope.where.column' => ['required_with:recipe.scope.where', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/'],
            'recipe.scope.where.window' => ['required_if:recipe.scope.where.operator,date_window', 'in:current_calendar_year'],
            'recipe.scope.where.values' => ['required_if:recipe.scope.where.operator,in', 'array', 'min:1', 'max:100'],
            'recipe.target' => ['required', 'array:profile_ref,table,strategy,ownership,key_columns'],
            'recipe.target.profile_ref' => ['required', 'in:bapps_mysql'],
            'recipe.target.table' => ['required', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/'],
            'recipe.target.strategy' => ['required', 'in:full_snapshot,daily_history_v1'],
            'recipe.target.ownership' => ['required', 'in:create_new,managed_only'],
            'recipe.target.key_columns' => ['sometimes', 'array', 'min:1', 'max:16'],
            'recipe.target.key_columns.*' => ['string', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/', 'distinct'],
            'recipe.constants' => ['sometimes', 'array', 'max:32'],
            'recipe.transformations' => ['sometimes', 'array', 'max:8'],
            'recipe.transformations.*' => ['string', 'in:profit.article_tax_rate_v1', 'distinct'],
            'recipe.limits' => ['required', 'array:batch_rows,statement_timeout_seconds,max_runtime_seconds'],
            'recipe.limits.batch_rows' => ['required', 'integer', 'min:100', 'max:5000'],
            'recipe.limits.statement_timeout_seconds' => ['required', 'integer', 'min:5', 'max:600'],
            'recipe.limits.max_runtime_seconds' => ['required', 'integer', 'min:30', 'max:21600'],
        ];
    }

    /** @return array<string, array<int, mixed>> */
    private static function writerRules(): array
    {
        return [
            'recipe' => ['required', 'array:schema_version,recipe_code,recipe_version,engine,minimum_agent_version,direction,source,target,settings,limits'],
            'recipe.schema_version' => ['required', 'in:1.0'],
            'recipe.recipe_code' => ['required', 'string', 'max:128', 'regex:/^[A-Za-z_][A-Za-z0-9_$]*$/'],
            'recipe.recipe_version' => ['prohibited'],
            'recipe.engine' => ['required', 'in:valery_prs_writer_v1'],
            'recipe.minimum_agent_version' => ['required', 'regex:/^\d+\.\d+\.\d+$/'],
            'recipe.direction' => ['required', 'in:write'],
            'recipe.source' => ['required', 'array:kind'],
            'recipe.source.kind' => ['required', 'in:bapps_orders_api'],
            'recipe.target' => ['required', 'array:profile_ref,driver,header_table,detail_table,detail_text_table'],
            'recipe.target.profile_ref' => ['required', 'string', 'max:64', 'regex:/^[A-Za-z_][A-Za-z0-9_-]*$/'],
            'recipe.target.driver' => ['required', 'in:firebird'],
            'recipe.target.header_table' => ['required', 'in:VENTAS'],
            'recipe.target.detail_table' => ['required', 'in:VENTAS_DETALLES'],
            'recipe.target.detail_text_table' => ['required', 'in:VENTAS_DETALLES_EXT'],
            'recipe.settings' => ['required', 'array:currency_code,payment_days,document_type,max_collision_retries,price_tolerance_percent'],
            'recipe.settings.currency_code' => ['required', 'in:02'],
            'recipe.settings.payment_days' => ['required', 'integer', 'in:15'],
            'recipe.settings.document_type' => ['required', 'in:PRS'],
            'recipe.settings.max_collision_retries' => ['required', 'integer', 'min:1', 'max:5'],
            'recipe.settings.price_tolerance_percent' => ['required', 'numeric', 'min:0', 'max:100'],
            'recipe.limits' => ['required', 'array:claim_limit,lease_seconds,max_runtime_seconds'],
            'recipe.limits.claim_limit' => ['required', 'integer', 'in:1'],
            'recipe.limits.lease_seconds' => ['required', 'integer', 'min:60', 'max:900'],
            'recipe.limits.max_runtime_seconds' => ['required', 'integer', 'min:30', 'max:1800'],
        ];
    }
}
