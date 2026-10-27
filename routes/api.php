<?php

use App\Http\Controllers\AgentApi\AgentCommandClaimController;
use App\Http\Controllers\AgentApi\AgentCommandResultController;
use App\Http\Controllers\AgentApi\AgentConfigController;
use App\Http\Controllers\AgentApi\AgentEnrollmentController;
use App\Http\Controllers\AgentApi\AgentEventController;
use App\Http\Controllers\AgentApi\AgentHeartbeatController;
use App\Http\Controllers\ControlApi\AgentBappsMysqlController;
use App\Http\Controllers\ControlApi\AgentCommandController;
use App\Http\Controllers\ControlApi\AgentController;
use App\Http\Controllers\ControlApi\AgentSyncController;
use App\Http\Controllers\ControlApi\AuditController;
use App\Http\Controllers\ControlApi\ClientController;
use App\Http\Controllers\ControlApi\DashboardMetricsController;
use App\Http\Controllers\ControlApi\LoginController;
use App\Http\Controllers\ControlApi\RunController;
use App\Http\Controllers\ControlApi\SyncCatalogController;
use App\Http\Controllers\ControlApi\SyncRecipeController;
use App\Http\Controllers\ControlApi\SyncSourceController;
use App\Http\Middleware\AuthenticateControlApi;
use Illuminate\Support\Facades\Route;

Route::prefix('v1/agent')->group(function (): void {
    Route::post('/enroll', AgentEnrollmentController::class)->middleware(['agent.payload', 'throttle:10,1']);

    Route::middleware(['agent.payload', 'agent.auth', 'throttle:120,1'])->group(function (): void {
        Route::post('/heartbeat', AgentHeartbeatController::class);
        Route::get('/config', AgentConfigController::class);
        Route::post('/commands/claim', AgentCommandClaimController::class);
        Route::post('/commands/{commandId}/result', AgentCommandResultController::class);
        Route::post('/events', AgentEventController::class);
    });
});

Route::prefix('v1')->group(function (): void {
    Route::post('/auth/login', LoginController::class)->middleware('throttle:10,1');

    Route::middleware(AuthenticateControlApi::class)->group(function (): void {
        Route::get('/dashboard/metrics', DashboardMetricsController::class);
        Route::get('/agents', [AgentController::class, 'index']);
        Route::get('/agents/{code}', [AgentController::class, 'show']);
        Route::post('/agents/{code}/commands', [AgentCommandController::class, 'store']);
        Route::get('/agents/{code}/commands/{commandId}', [AgentCommandController::class, 'show']);
        Route::post('/agents/{code}/syncs', [AgentSyncController::class, 'store']);
        Route::patch('/agents/{code}/syncs/{syncCode}', [AgentSyncController::class, 'update']);
        Route::put('/agents/{code}/bapps-mysql', [AgentBappsMysqlController::class, 'update']);
        Route::get('/runs', [RunController::class, 'index']);
        Route::get('/runs/{id}', [RunController::class, 'show']);
        Route::post('/runs/{id}/retry', [RunController::class, 'retry']);
        Route::post('/runs/{id}/review', [RunController::class, 'review']);
        Route::get('/audit', [AuditController::class, 'index']);
        Route::get('/clients', [ClientController::class, 'index']);
        Route::get('/clients/{id}', [ClientController::class, 'show']);
        Route::get('/syncs', [SyncCatalogController::class, 'index']);
        Route::post('/syncs', [SyncCatalogController::class, 'store']);
        Route::patch('/syncs/{code}', [SyncCatalogController::class, 'update']);
        Route::delete('/syncs/{code}', [SyncCatalogController::class, 'destroy']);
        Route::post('/syncs/{code}/recipes', [SyncRecipeController::class, 'store']);
        Route::get('/sync-sources', [SyncSourceController::class, 'index']);
        Route::post('/sync-sources', [SyncSourceController::class, 'store']);
        Route::patch('/sync-sources/{id}', [SyncSourceController::class, 'update']);
        Route::delete('/sync-sources/{id}', [SyncSourceController::class, 'destroy']);
    });
});
