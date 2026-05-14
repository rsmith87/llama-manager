# Controller Durable Orchestration Memory Design

## Goal

Add durable, queryable controller-side memory for delegated work history, while keeping nodes lightweight and focused on execution.

## Non-Goals

- No distributed shared mutable state across nodes.
- No requirement for nodes to read controller internals.
- No replacement of current model control endpoints (`/models`, `/nodes/*`) in this phase.

## Recommendation

Use controller-owned durable orchestration state with append-only event history and lease-based task assignment. Keep node state local and ephemeral beyond existing config/runtime process state.

Why this fits current architecture:
- Current controller already centralizes node registration, heartbeats, and proxying.
- Current nodes expose clean execution/control APIs and do not require global context.
- This avoids consistency and split-brain risks from true shared memory.

## Data Model

Use SQLite (WAL mode) first, with repository interfaces so Postgres can be added later.

### Tables

1. `jobs`
- `id` TEXT PK (uuid)
- `type` TEXT NOT NULL
- `payload_json` TEXT NOT NULL
- `requested_by` TEXT NULL
- `priority` INTEGER NOT NULL DEFAULT 0
- `status` TEXT NOT NULL
  - enum: `queued|assigned|running|completed|failed|canceled|timed_out`
- `target_selector` TEXT NOT NULL DEFAULT `auto`
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
- `completed_at` TEXT NULL
- `result_json` TEXT NULL
- `error_code` TEXT NULL
- `error_detail` TEXT NULL
- indexes: `(status, priority, created_at)`, `(created_at)`

2. `job_attempts`
- `id` TEXT PK (uuid)
- `job_id` TEXT NOT NULL FK -> `jobs.id`
- `attempt_number` INTEGER NOT NULL
- `node_name` TEXT NOT NULL
- `lease_expires_at` TEXT NOT NULL
- `started_at` TEXT NOT NULL
- `ended_at` TEXT NULL
- `status` TEXT NOT NULL
  - enum: `assigned|running|completed|failed|abandoned|expired`
- `failure_reason` TEXT NULL
- unique: `(job_id, attempt_number)`
- indexes: `(node_name, status)`, `(lease_expires_at)`

3. `node_leases`
- `node_name` TEXT PK
- `last_heartbeat_at` TEXT NOT NULL
- `capacity_json` TEXT NULL
- `labels_json` TEXT NULL
- `status` TEXT NOT NULL
  - enum: `online|degraded|offline`
- `updated_at` TEXT NOT NULL
- index: `(status, updated_at)`

4. `job_events`
- `id` TEXT PK (uuid)
- `job_id` TEXT NOT NULL FK -> `jobs.id`
- `attempt_id` TEXT NULL FK -> `job_attempts.id`
- `event_type` TEXT NOT NULL
  - enum: `job_created|job_assigned|attempt_started|progress|attempt_failed|attempt_completed|job_completed|job_failed|job_canceled|lease_expired|retry_scheduled`
- `event_json` TEXT NOT NULL
- `created_at` TEXT NOT NULL
- indexes: `(job_id, created_at)`, `(event_type, created_at)`

5. `artifacts` (optional in phase 2)
- `id` TEXT PK (uuid)
- `job_id` TEXT NOT NULL FK -> `jobs.id`
- `attempt_id` TEXT NULL FK -> `job_attempts.id`
- `kind` TEXT NOT NULL
- `uri` TEXT NOT NULL
- `meta_json` TEXT NULL
- `created_at` TEXT NOT NULL
- index: `(job_id, created_at)`

## API Contract

All new endpoints are controller-only.

### Job Lifecycle

1. `POST /jobs`
- Request:
  - `type: string`
  - `payload: object`
  - `priority?: int`
  - `target?: "auto" | "local" | "node:<name>"`
  - `requested_by?: string`
- Response: `201` with job record.

2. `GET /jobs`
- Query filters:
  - `status`, `type`, `requested_by`, `node`, `from`, `to`, `limit`, `cursor`
- Response: paginated job summaries.

3. `GET /jobs/{job_id}`
- Response: job + latest attempt summary + result/error fields.

4. `POST /jobs/{job_id}/cancel`
- Allowed when `queued|assigned|running`.
- Response: updated job status.

### Event History

5. `GET /jobs/{job_id}/events`
- Query: `limit`, `cursor`
- Response: ordered event stream.

### Node Work Pull/Push

6. `POST /nodes/{node}/work/claim`
- Request:
  - `capacity?: object`
  - `labels?: object`
  - `max_jobs?: int` (default 1)
- Behavior:
  - Refresh node lease and heartbeat timestamp.
  - Atomically claim eligible queued jobs for this node.
- Response: claimed jobs with `attempt_id`, `lease_expires_at`.

7. `POST /nodes/{node}/work/{attempt_id}/progress`
- Request: `progress: object`
- Behavior: append `progress` event and extend lease.

8. `POST /nodes/{node}/work/{attempt_id}/complete`
- Request: `result: object`, `artifacts?: []`
- Behavior: mark attempt complete, job complete, append events.

9. `POST /nodes/{node}/work/{attempt_id}/fail`
- Request: `error_code: string`, `error_detail?: string`, `retryable?: bool`
- Behavior:
  - mark attempt failed
  - if retryable and attempts remain: enqueue retry and emit `retry_scheduled`
  - else mark job failed

## Lease + Retry Rules

- Lease timeout default: 60s, renewable via progress heartbeat.
- Sweeper loop (controller background task, every 15s):
  - detect expired leases for `assigned|running` attempts
  - mark attempt `expired`
  - reschedule job with incremented attempt if under max attempts
  - else mark job `timed_out`
- Default max attempts: 3.
- Idempotency:
  - `complete/fail/progress` require matching active `attempt_id` and node owner.
  - Replays return current state without double-writing terminal transitions.

## Controller Integration

1. Add `core/orchestration_store.py`
- DB connection lifecycle
- migrations bootstrap
- transaction helpers

2. Add `core/orchestration_repo.py`
- typed repository methods for jobs/attempts/events/leases

3. Add `core/orchestrator.py`
- assignment logic
- lease renewal/expiration
- retry policy
- state transition validation

4. Add `api/routes_jobs.py`
- submit/query/cancel/event APIs

5. Add `api/routes_node_work.py`
- claim/progress/complete/fail APIs

6. Wire in `main.py`
- initialize store/repo/orchestrator in `controller` mode
- add sweeper background task only in `controller` mode

## Node Integration

Keep node changes minimal:
- Existing nodes continue serving model APIs.
- Add optional worker loop process/script later that:
  - claims work from controller
  - executes task handler
  - posts progress/result/failure
- If worker loop is absent, no behavior change to current deployments.

## Security

- Reuse existing node auth model:
  - `X-Llama-Manager-Key` between controller and nodes as needed
- For new work endpoints, require per-node authentication keyed by configured node `api_key` or registration-bound secret.
- Validate node identity matches `{node}` path to prevent cross-node impersonation.

## Observability

- Keep append-only `job_events` as primary audit trail.
- Add controller logs for state transitions with `job_id`, `attempt_id`, `node`.
- Add metrics counters:
  - jobs queued/completed/failed/timed_out
  - retry count
  - lease expirations
  - claim latency

## Backward Compatibility

- Existing `/models`, `/chat`, `/nodes/*` routes remain unchanged.
- Orchestration APIs are additive.
- Controller without DB path configured defaults to `./logs/controller_state.db`.

## Rollout Plan

Phase 1:
- SQLite store + migrations
- job submit/query/events
- node claim/complete/fail
- sweeper + retry
- tests for transitions and idempotency

Phase 2:
- artifacts table
- richer node capability matching
- retention policies + archival export

Phase 3:
- Postgres adapter
- optional multi-controller leader election

## Testing Strategy

- Unit tests:
  - transition validity matrix
  - lease expiry and retry logic
  - idempotent complete/fail/progress handling
- API tests:
  - full lifecycle from submit -> claim -> complete
  - failure + retry -> final fail
  - cancel during queued/running
- Crash recovery tests:
  - controller restart with in-flight attempts
  - sweeper reconciliation after restart

## Risks and Mitigations

1. DB contention under high write volume
- Mitigation: short transactions, batched event writes, indexes above.

2. Duplicate execution during network partitions
- Mitigation: lease ownership checks + terminal transition idempotency.

3. History growth
- Mitigation: retention config (e.g., keep detailed events 30-90 days, compact summaries beyond).

## Open Decisions (Proposed Defaults)

- DB engine default: SQLite WAL (`controller_state.db`) -> yes.
- Max attempts: `3`.
- Lease timeout: `60s`.
- Sweeper interval: `15s`.
- Progress heartbeat expected every `20s`.
