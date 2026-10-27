<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('clients', function (Blueprint $table): void {
            $table->id();
            $table->string('name');
            $table->string('system_type');
            $table->string('status')->default('active');
            $table->string('timezone')->nullable();
            $table->timestamps();
        });

        Schema::create('agents', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('client_id')->constrained()->cascadeOnDelete();
            $table->string('agent_code')->unique();
            $table->string('machine_name')->nullable();
            $table->string('os')->nullable();
            $table->string('version')->nullable();
            $table->string('status')->default('enrolled');
            $table->dateTime('last_seen_at')->nullable();
            $table->string('last_ip', 45)->nullable();
            $table->boolean('enabled')->default(true);
            $table->string('credential_hash');
            $table->unsignedInteger('config_version')->default(1);
            $table->timestamps();

            $table->index(['status', 'last_seen_at']);
            $table->index(['client_id', 'status']);
        });

        Schema::create('sync_catalog', function (Blueprint $table): void {
            $table->id();
            $table->string('code')->unique();
            $table->string('name');
            $table->string('source_type');
            $table->string('min_agent_version');
            $table->boolean('enabled_globally')->default(true);
            $table->unsignedInteger('default_interval_seconds');
            $table->text('description')->nullable();
            $table->timestamps();
        });

        Schema::create('agent_syncs', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('agent_id')->constrained()->cascadeOnDelete();
            $table->foreignId('sync_catalog_id')->constrained('sync_catalog')->cascadeOnDelete();
            $table->string('status')->default('enabled');
            $table->unsignedInteger('interval_seconds');
            $table->unsignedInteger('config_version')->default(1);
            $table->json('config_json')->nullable();
            $table->dateTime('next_run_hint')->nullable();
            $table->timestamps();

            $table->unique(['agent_id', 'sync_catalog_id']);
        });

        Schema::create('sync_commands', function (Blueprint $table): void {
            $table->id();
            $table->string('command_id')->unique();
            $table->foreignId('agent_id')->constrained()->cascadeOnDelete();
            $table->string('command_type');
            $table->string('sync_code')->nullable();
            $table->string('run_id')->nullable();
            $table->json('payload_json')->nullable();
            $table->string('status')->default('pending');
            $table->string('idempotency_key')->unique();
            $table->foreignId('created_by')->nullable()->constrained('users')->nullOnDelete();
            $table->dateTime('issued_at');
            $table->dateTime('expires_at');
            $table->dateTime('claimed_at')->nullable();
            $table->dateTime('lease_expires_at')->nullable();
            $table->dateTime('completed_at')->nullable();
            $table->json('result_json')->nullable();
            $table->timestamps();

            $table->index(['agent_id', 'status', 'expires_at', 'created_at']);
        });

        Schema::create('sync_runs', function (Blueprint $table): void {
            $table->id();
            $table->string('run_id')->unique();
            $table->foreignId('agent_id')->constrained()->cascadeOnDelete();
            $table->foreignId('client_id')->constrained()->cascadeOnDelete();
            $table->foreignId('sync_catalog_id')->constrained('sync_catalog')->cascadeOnDelete();
            $table->string('correlation_id')->nullable();
            $table->string('status');
            $table->string('trigger')->nullable();
            $table->string('command_id')->nullable();
            $table->dateTime('started_at')->nullable();
            $table->dateTime('finished_at')->nullable();
            $table->unsignedBigInteger('duration_ms')->nullable();
            $table->unsignedBigInteger('rows_read')->default(0);
            $table->unsignedBigInteger('rows_inserted')->default(0);
            $table->unsignedBigInteger('rows_updated')->default(0);
            $table->unsignedBigInteger('rows_deleted')->default(0);
            $table->unsignedBigInteger('rows_failed')->default(0);
            $table->string('error_code')->nullable();
            $table->text('error_message')->nullable();
            $table->string('agent_version')->nullable();
            $table->timestamps();

            $table->index(['agent_id', 'started_at']);
            $table->index(['client_id', 'started_at']);
            $table->index(['status', 'started_at']);
            $table->index(['sync_catalog_id', 'started_at']);
        });

        Schema::create('sync_events', function (Blueprint $table): void {
            $table->id();
            $table->string('event_id')->unique();
            $table->string('schema_version');
            $table->string('event_type');
            $table->foreignId('agent_id')->constrained()->cascadeOnDelete();
            $table->foreignId('client_id')->constrained()->cascadeOnDelete();
            $table->string('sync_code')->nullable();
            $table->string('run_id')->nullable();
            $table->string('correlation_id')->nullable();
            $table->dateTime('occurred_at');
            $table->dateTime('received_at');
            $table->json('payload_json');
            $table->timestamps();

            $table->index(['agent_id', 'occurred_at']);
            $table->index('run_id');
            $table->index(['event_type', 'occurred_at']);
        });

        Schema::create('sync_audit_events', function (Blueprint $table): void {
            $table->id();
            $table->string('kind');
            $table->string('action');
            $table->string('actor_type');
            $table->unsignedBigInteger('actor_id')->nullable();
            $table->string('target_type');
            $table->string('target_id');
            $table->string('result');
            $table->json('context_json')->nullable();
            $table->dateTime('occurred_at');
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('sync_audit_events');
        Schema::dropIfExists('sync_events');
        Schema::dropIfExists('sync_runs');
        Schema::dropIfExists('sync_commands');
        Schema::dropIfExists('agent_syncs');
        Schema::dropIfExists('sync_catalog');
        Schema::dropIfExists('agents');
        Schema::dropIfExists('clients');
    }
};
