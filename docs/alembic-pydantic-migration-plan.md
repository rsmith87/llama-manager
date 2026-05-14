# Alembic + Pydantic Migration Task List

Date: 2026-05-12
Status: Completed
Scope: Task breakdown only

## Current progress

- Completed: Task 1, Task 2, Task 3, Task 4, Task 5, Task 6, Task 7, Task 8, Task 9, Task 10, Task 11, Task 12, Task 13, Task 14, Task 15
- In progress: none

## Task 1: Lock migration design decisions

Status:
- Completed on 2026-05-12.
- Decision record: docs/adr/2026-05-12-alembic-pydantic-task-1-decisions.md

Purpose:
- Prevent rework by agreeing on database topology and parity constraints before implementation.

Details:
1. Decide multi-database Alembic strategy:
- One Alembic environment with multiple named DB targets, or
- Separate migration script locations per DB file.
2. Define SQLAlchemy naming conventions for constraints and indexes.
3. Confirm timestamp strategy for this cycle (keep ISO UTC text parity).
4. Define JSON column parity rules for all json text fields.
5. Record non-goals (no API redesign, no unrelated refactors).

Deliverables:
- Signed-off design notes in docs.
- Final list of parity rules to enforce in tests.

Completion criteria:
- Team agrees on topology and schema parity constraints.

Dependencies:
- None.

## Task 2: Add persistence infrastructure primitives

Status:
- Completed on 2026-05-12.
- Implemented in:
	- pyproject.toml (sqlalchemy + alembic dependencies)
	- llama_manager/core/persistence/db_infra.py (engine/session/tx/url helpers)
	- llama_manager/core/config/models.py (auth/audit/chat DB URL override fields)
	- config.example.yaml (documented optional DB URL overrides)
	- tests/test_persistence_db_infra.py (infra validation tests)

Purpose:
- Introduce SQLAlchemy engine/session utilities without altering runtime behavior.

Details:
1. Add dependencies: sqlalchemy, alembic.
2. Create DB infrastructure module:
- engine factory
- session factory
- transaction helper patterns
3. Ensure SQLite pragmas match current behavior:
- journal_mode=WAL
- foreign_keys=ON
4. Add configuration points for database URL/path mapping.

Deliverables:
- New infrastructure modules for engine and session management.
- Minimal developer docs for local usage.

Completion criteria:
- App boots with existing store classes unchanged.
- Engine/session can connect to current SQLite files.

Dependencies:
- Task 1.

## Task 3: Initialize Alembic and environment wiring

Status:
- Completed on 2026-05-12.
- Implemented in:
	- alembic.ini (project Alembic configuration)
	- migrations/env.py (target selection + metadata + URL wiring)
	- migrations/script.py.mako (revision template)
	- migrations/versions/* (target-specific version folders)
	- migrations/README.md (targeted migration commands)
	- llama_manager/core/persistence/alembic_config.py (target and metadata helpers)
	- README.md (developer command examples)
	- tests/test_alembic_config.py (target parsing and metadata wiring tests)

Purpose:
- Establish migration tooling as the canonical schema management path.

Details:
1. Initialize Alembic config and env scripts.
2. Wire metadata discovery for ORM models.
3. Configure migration targets for the chosen multi-DB approach.
4. Add developer command documentation for upgrade, downgrade, stamp.

Deliverables:
- Alembic configuration committed.
- Working migration command documentation.

Completion criteria:
- Alembic commands run in development.
- Environment can resolve target metadata and DB URLs.

Dependencies:
- Task 1, Task 2.

## Task 4: Implement ORM models for orchestration schema

Status:
- Completed on 2026-05-12.
- Implemented in:
	- llama_manager/core/persistence/models/orchestration.py (orchestration ORM models)
	- llama_manager/core/persistence/models/__init__.py (model exports)
	- migrations/env.py (metadata discovery import)
	- llama_manager/core/persistence/__init__.py (public exports)
	- tests/test_orchestration_orm_models.py (schema parity tests)

Purpose:
- Create ORM parity for the highest-risk persistence domain first.

Details:
1. Model these tables with exact parity where possible:
- jobs
- job_attempts
- node_leases
- job_events
- artifacts
- schema_meta
- controller_leases
2. Preserve key constraints, indexes, nullability, and defaults.
3. Map JSON text columns and timestamp text columns explicitly.

Deliverables:
- ORM model modules for orchestration tables.

Completion criteria:
- ORM metadata accurately represents current orchestration schema.

Dependencies:
- Task 2, Task 3.

## Task 5: Implement ORM models for auth/audit/chat persistence

Status:
- Started on 2026-05-13.
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/models/app_state.py (auth/audit/chat ORM models)
	- llama_manager/core/persistence/models/__init__.py (model exports)
	- llama_manager/core/persistence/__init__.py (public exports)
	- tests/test_app_state_orm_models.py (schema parity tests)

Purpose:
- Cover remaining SQLite stores with model parity.

Details:
1. Model these tables:
- api_keys
- audit_events
- chat_sessions
2. Preserve existing column names and field semantics.
3. Match existing index behavior and uniqueness constraints.

Deliverables:
- ORM model modules for auth, audit, and chat session tables.

Completion criteria:
- Full persistence schema is represented in ORM metadata.

Dependencies:
- Task 2, Task 3.

## Task 6: Create baseline Alembic revision set

Status:
- Completed on 2026-05-13.
- Implemented in:
	- migrations/versions/controller/20260513_0001_controller_baseline.py
	- migrations/versions/auth/20260513_0002_auth_baseline.py
	- migrations/versions/audit/20260513_0003_audit_baseline.py
	- migrations/versions/chat_sessions/20260513_0004_chat_sessions_baseline.py
	- alembic.ini (fixed version_locations path separator)
	- migrations/README.md (fresh/stamp+upgrade workflows)
- Validation artifacts:
	- tests/fixtures/migration-task6-config.yaml (fresh-path config)
	- tests/fixtures/migration-task6-existing-config.yaml (existing-path config)

Purpose:
- Capture the existing schema as migration history entry point.

Details:
1. Generate baseline revisions for all target databases.
2. Review revisions manually to ensure parity with live schema.
3. Verify fresh install path:
- target-qualified Alembic upgrades (`<target>@head`) create the selected target schema.
4. Verify existing install path:
- alembic stamp baseline then upgrade succeeds.

Deliverables:
- Baseline revision files.
- Stamp/upgrade procedure documentation.

Completion criteria:
- Fresh and existing DB flows are both validated successfully.

Dependencies:
- Task 4, Task 5.

## Task 7: Add Pydantic persistence DTO layer

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/dto/records.py (read DTOs)
	- llama_manager/core/persistence/dto/commands.py (write/update DTOs)
	- llama_manager/core/persistence/dto/converters.py (ORM <-> DTO conversion helpers)
	- llama_manager/core/persistence/dto/__init__.py (DTO exports)
	- llama_manager/core/persistence/__init__.py (public exports)
	- tests/test_persistence_dto.py (converter and DTO tests)

Purpose:
- Replace ad hoc internal dict contracts with typed models while preserving external API shapes.

Details:
1. Define read DTOs for store/repo outputs currently returned as dicts.
2. Define write/update DTOs for command inputs.
3. Add ORM-to-DTO and DTO-to-ORM mapping helpers.
4. Ensure serialization parity with current route responses.

Deliverables:
- DTO modules and conversion helpers.

Completion criteria:
- Migrated internals use typed DTOs.
- API payload shapes remain unchanged.

Dependencies:
- Task 4, Task 5.

## Task 8: Build ORM-backed auth store implementation

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/auth_store_orm.py (ORM-backed auth store)
	- llama_manager/main.py (auth backend toggle wiring)
	- llama_manager/core/config/models.py (auth_store_backend config flag)
	- config.example.yaml (auth_store_backend docs)
	- llama_manager/api/routes/auth/common.py (store type hint broadening)
	- llama_manager/core/persistence/__init__.py (exports)
	- tests/test_auth_store_orm.py (legacy/ORM parity behavior)
	- tests/test_api.py (app-level toggle integration)

Purpose:
- Migrate lowest-risk domain first to validate patterns.

Details:
1. Implement ORM-backed auth repository/store behind current interface.
2. Preserve behavior for:
- key creation
- key hashing and resolve
- revoke and list operations
3. Keep legacy path available behind feature toggle.
4. Add parity tests comparing legacy and ORM outputs.

Deliverables:
- ORM-backed auth implementation.
- Feature toggle wiring.
- Parity tests.

Completion criteria:
- Auth tests pass with ORM implementation enabled.
- No auth API contract drift.

Dependencies:
- Task 6, Task 7.

## Task 9: Build ORM-backed audit store implementation

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/audit_store_orm.py (ORM-backed audit store)
	- llama_manager/main.py (audit backend toggle wiring)
	- llama_manager/core/config/models.py (audit_store_backend config flag)
	- config.example.yaml (audit_store_backend docs)
	- llama_manager/api/dependencies.py (store type hint broadening)
	- llama_manager/core/persistence/__init__.py (exports)
	- tests/test_audit_store_orm.py (legacy/ORM parity behavior)
	- tests/test_api.py (app-level toggle integration)
	- tests/test_config.py (toggle default assertions)

Purpose:
- Migrate audit domain while preserving filtering and payload semantics.

Details:
1. Implement ORM-backed audit repository/store behind current interface.
2. Preserve list filtering behavior:
- event_type
- target
- dry_run
- created_from/to
3. Preserve payload_json conversion behavior.
4. Keep legacy path behind feature toggle and add parity tests.

Deliverables:
- ORM-backed audit implementation.
- Parity tests for read/write behavior.

Completion criteria:
- Audit tests and endpoint behavior are unchanged under ORM path.

Dependencies:
- Task 6, Task 7.

## Task 10: Build ORM-backed chat session store implementation

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/chat_session_store_orm.py (ORM-backed chat session store)
	- llama_manager/main.py (chat sessions backend toggle wiring)
	- llama_manager/core/config/models.py (chat_sessions_store_backend config flag)
	- config.example.yaml (chat sessions backend toggle docs)
	- llama_manager/api/dependencies.py (store type hint broadening)
	- llama_manager/api/routes/chat/sessions.py (dependency typing broadening)
	- llama_manager/core/persistence/__init__.py (exports)
	- tests/test_chat_session_store_orm.py (legacy/ORM parity behavior)
	- tests/test_api.py (app-level toggle integration)
	- tests/test_config.py (toggle default assertions)

Purpose:
- Migrate chat session persistence with full upsert parity.

Details:
1. Implement ORM-backed chat session repository/store.
2. Preserve behavior for:
- list order by updated_at desc
- get by id with json decode
- save upsert semantics
- delete semantics
3. Keep legacy path behind feature toggle and add parity tests.

Deliverables:
- ORM-backed chat session implementation.
- Endpoint-level regression tests for session routes.

Completion criteria:
- Chat session tests pass with ORM implementation.
- No route response drift.

Dependencies:
- Task 6, Task 7.

## Task 11: Build ORM-backed orchestration implementation

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/orchestration/store_orm.py (ORM-initialized orchestration store with SQL compatibility adapter)
	- llama_manager/main.py (orchestration backend toggle wiring)
	- llama_manager/core/config/models.py (orchestration_store_backend config flag)
	- config.example.yaml (orchestration backend toggle docs)
	- llama_manager/core/orchestration/repo.py (store typing widened)
	- llama_manager/core/orchestration/__init__.py (exports)
	- tests/test_orchestration_store.py (ORM store parity tests)
	- tests/test_api.py (app-level toggle integration)
	- tests/test_config.py (toggle default assertions)

Purpose:
- Migrate queue lifecycle domain with strict behavioral equivalence.

Details:
1. Implement ORM-backed equivalents for:
- create/list/get/cancel job
- claim/progress/complete/fail attempt
- sweep expired attempts
- retention pruning and artifact/event queries
2. Preserve claim ordering and transition semantics exactly.
3. Preserve terminal status handling:
- completed
- failed
- canceled
- timed_out
4. Preserve cancel_requested behavior and retry scheduling rules.
5. Keep legacy path behind feature toggle.

Deliverables:
- ORM-backed orchestration repo/lifecycle/retention.
- Extensive parity and transition tests.

Completion criteria:
- Existing orchestration tests pass.
- Added contention tests pass.

Dependencies:
- Task 6, Task 7.

## Task 12: Add migration and parity test suites to CI

Status:
- Completed on 2026-05-13.
- Implemented in:
	- .github/workflows/ci.yml (new CI workflow)
	- CI job `migration-smoke`:
		- fresh install `alembic upgrade <target>@head` flow for controller/auth/audit/chat_sessions
		- existing install `stamp <target>@head` + `upgrade <target>@head` flow for controller/auth/audit/chat_sessions
		- table and revision assertions for all target databases
	- CI job `parity-suite`:
		- runs persistence parity/toggle tests across DTO, model, store, API, and config checks

Validation performed locally:
- parity-suite command passed (`13 passed`, selected subset)
- migration-smoke fresh flow passed (all expected tables present)
- migration-smoke existing flow passed with each target DB stamped to its own branch head

Purpose:
- Prevent regressions during gradual cutover.

Details:
1. Add migration smoke tests in CI:
- fresh DB upgrade to head
- baseline stamp + upgrade path
2. Add parity tests for each migrated domain.
3. Add endpoint contract checks for:
- jobs
- chat sessions
- audit events
- auth keys
4. Add targeted contention tests for orchestration claim/sweep flows.

Deliverables:
- CI jobs and test modules for migration and parity.

Completion criteria:
- CI enforces migration safety and behavior parity before merge.

Dependencies:
- Task 8, Task 9, Task 10, Task 11.

## Task 13: Enable staged cutover with runtime toggles

Status:
- Completed on 2026-05-13.
- Implemented in:
	- docs/how-to-use.md (staged rollout and rollback runbook)
	- README.md (toggle field reference)
	- tests/test_api.py (all-backends ORM toggle integration test)
	- tests/test_config.py (legacy-default toggle assertions)

Validation performed:
- Focused toggle suite passed (`6 passed`) including:
	- per-domain ORM toggle tests (auth/audit/chat sessions/orchestration)
	- all persistence backends toggled to ORM together
	- default fallback assertions

Purpose:
- Reduce rollout risk by enabling per-domain fallback.

Details:
1. Add configuration toggles for legacy vs ORM path per domain.
2. Default toggles conservatively during initial rollout.
3. Validate toggles in test and dev environments.
4. Document operational toggle usage for incident response.

Deliverables:
- Configurable per-domain runtime toggles.
- Operator documentation for fallback.

Completion criteria:
- Each domain can be switched independently at runtime/startup.

Dependencies:
- Task 8, Task 9, Task 10, Task 11.

## Task 14: Remove runtime schema DDL from app startup

Status:
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/core/persistence/db_infra.py (schema readiness helpers)
	- llama_manager/core/persistence/auth_store.py (removed runtime DDL, require migrated schema)
	- llama_manager/core/persistence/audit_store.py (removed runtime DDL, require migrated schema)
	- llama_manager/core/persistence/chat_session_store.py (removed runtime DDL, require migrated schema)
	- llama_manager/core/persistence/auth_store_orm.py (removed startup table create calls)
	- llama_manager/core/persistence/audit_store_orm.py (removed startup table create calls)
	- llama_manager/core/persistence/chat_session_store_orm.py (removed startup table create calls)
	- llama_manager/core/orchestration/store.py (removed runtime DDL, require migrated schema)
	- llama_manager/core/orchestration/store_orm.py (removed startup table create calls)
	- llama_manager/main.py (deferred module-level startup failure into health-unavailable app)
	- docs/how-to-use.md and README.md (migration-before-start requirement)
	- .github/workflows/ci.yml (existing-path smoke no longer uses store constructor DDL)

Validation performed:
- Focused startup/parity suite passed (`15 passed` selected tests), including:
	- legacy + ORM store behavior tests under pre-migrated schemas
	- API toggle integration tests
	- app startup failure when migrations are missing
- migration-smoke fresh flow passed (upgrade and table assertions)
- migration-smoke existing flow passed (stamp+upgrade and revision assertions)

Purpose:
- Complete transition to migration-owned schema management.

Details:
1. Remove runtime create table scripts from stores.
2. Retain only connectivity and migration-state checks at startup.
3. Ensure startup errors are actionable when migrations are missing.
4. Update operational docs to require migration before app startup.

Deliverables:
- Runtime code paths free of schema-creation logic.
- Updated runbook documentation.

Completion criteria:
- No normal boot path performs schema DDL.
- Alembic is the only schema evolution mechanism.

Dependencies:
- Task 12, Task 13.

## Task 15: Final cleanup and decommission legacy paths

Status:
- Started on 2026-05-13.
- Completed on 2026-05-13.
- Implemented in:
	- llama_manager/main.py (ORM-only persistence wiring)
	- llama_manager/core/config/models.py (removed backend toggle config fields)
	- llama_manager/core/orchestration/repo.py (ORM-only store typing)
	- llama_manager/core/orchestration/store.py (removed legacy store)
	- llama_manager/core/orchestration/store_orm.py (removed legacy dependency)
	- llama_manager/core/persistence/auth_store.py (removed legacy store)
	- llama_manager/core/persistence/audit_store.py (removed legacy store)
	- llama_manager/core/persistence/chat_session_store.py (removed legacy store)
	- llama_manager/core/persistence/__init__.py (removed legacy exports)
	- llama_manager/auth.py (CLI updated to ORM auth store)
	- llama_manager/api/routes/audit.py and llama_manager/api/dependencies.py (ORM typing cleanup)
	- tests/test_auth_store_orm.py, tests/test_audit_store_orm.py, tests/test_chat_session_store_orm.py, tests/test_orchestration_store.py (ORM-only store behavior tests)
	- tests/test_api.py and tests/test_config.py (removed toggle-era assertions)
	- config.example.yaml, README.md, docs/how-to-use.md (removed backend toggle docs)

Purpose:
- Eliminate maintenance overhead after stable parity period.

Details:
1. Remove legacy store implementations and compatibility wrappers.
2. Remove feature toggles after confidence threshold is met.
3. Clean dead code and update architecture docs.
4. Run full regression suite before completion.

Deliverables:
- Single persistence path (ORM + Alembic + DTOs).
- Cleaned documentation and reduced technical debt.

Completion criteria:
- Legacy code removed with tests green.
- Architecture docs reflect final state.

Dependencies:
- Task 14.

## Cross-task verification checklist

Apply to every completed task:

1. No API response shape drift.
2. Existing tests remain green unless intentionally updated.
3. New tests cover changed persistence behavior.
4. Rollback path is documented for affected domains.
5. Operational notes are updated where behavior changed.
