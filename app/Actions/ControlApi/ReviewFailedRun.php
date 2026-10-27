<?php

namespace App\Actions\ControlApi;

use App\Models\SyncRun;
use Illuminate\Support\Facades\DB;
use RuntimeException;

final class ReviewFailedRun
{
    public function __construct(private readonly RecordControlAudit $recordAudit) {}

    public function handle(string $runId, ?int $actorId): SyncRun
    {
        return DB::transaction(function () use ($runId, $actorId): SyncRun {
            $run = SyncRun::query()->where('run_id', $runId)->lockForUpdate()->first();

            if ($run === null) {
                throw new RuntimeException("La ejecución {$runId} no existe.");
            }
            if ($run->status !== 'failed') {
                throw new RuntimeException('Solo se pueden revisar ejecuciones fallidas.');
            }

            if ($run->reviewed_at === null) {
                $run->update(['reviewed_at' => now(), 'reviewed_by' => $actorId]);
                $this->recordAudit->handle('error', 'review_run', $actorId, 'run', $run->run_id, [
                    'client_id' => $run->client_id,
                    'error_code' => $run->error_code,
                ]);
            }

            return $run->fresh(['agent.client', 'catalog']);
        });
    }
}
