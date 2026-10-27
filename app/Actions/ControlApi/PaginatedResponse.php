<?php

namespace App\Actions\ControlApi;

use Illuminate\Contracts\Pagination\LengthAwarePaginator;
use Illuminate\Http\Resources\Json\JsonResource;

final class PaginatedResponse
{
    /** @param class-string<JsonResource> $resource */
    public static function make(LengthAwarePaginator $paginator, string $resource): array
    {
        return [
            'data' => $resource::collection($paginator->items())->resolve(),
            'page' => $paginator->currentPage(),
            'page_size' => $paginator->perPage(),
            'total' => $paginator->total(),
        ];
    }
}
