# ADR: Alembic + Pydantic Migration Decisions (Task 1)

Date: 2026-05-12
Status: Accepted
Related: docs/alembic-pydantic-migration-plan.md

## Context

The application currently uses multiple SQLite files and imperative runtime schema creation. Migration to Alembic + SQLAlchemy + Pydantic requires a locked design baseline to avoid implementation churn.

## Decision 1: Alembic topology

Decision:
- Use one Alembic project with multiple named migration targets (multiple script locations under one migration root), one target per SQLite database domain.

Rationale:
- Preserves current multi-file DB layout.
- Avoids forced DB consolidation during this migration.
- Keeps operational commands centralized while still isolating revisions by domain.

Implications:
- Migration commands must specify target domain or run all targets in sequence.
- CI must run migration smoke tests per target.

## Decision 2: Database scope for this migration

Decision:
- Keep current SQLite persistence topology unchanged in this cycle.

Rationale:
- Lowest-risk path for behavior parity.
- Avoids data movement and cross-domain migration complexity.

Implications:
- No schema consolidation task is included in current backlog.

## Decision 3: Timestamp representation

Decision:
- Keep UTC ISO-8601 text timestamps for all existing timestamp fields in this cycle.

Rationale:
- Matches existing ordering and filtering assumptions.
- Avoids silent behavior changes across retention, sorting, and API payloads.

Implications:
- Native datetime column migration is explicitly deferred.

## Decision 4: JSON representation

Decision:
- Keep existing json-as-text column strategy and explicit JSON encode/decode behavior.

Rationale:
- Preserves null semantics and payload shape parity.
- Avoids dialect-specific JSON behavior differences during initial cutover.

Implications:
- ORM models map these as text-backed fields with strict conversion helpers.

## Decision 5: Naming conventions

Decision:
- Adopt explicit SQLAlchemy naming conventions for constraints and indexes:
  - pk: pk_<table_name>
  - fk: fk_<table_name>_<column_0_name>_<referred_table_name>
  - uq: uq_<table_name>_<column_0_name>
  - ix: ix_<table_name>_<column_0_name>
  - ck: ck_<table_name>_<constraint_name>

Rationale:
- Stabilizes Alembic autogenerate output.
- Reduces naming drift across revisions.

Implications:
- Existing unnamed DB constraints may require careful baseline handling.

## Decision 6: API and behavior parity boundaries

Decision:
- Preserve route payload shape and status semantics exactly during persistence cutover.

Rationale:
- Migration goal is infrastructure modernization, not API redesign.

Implications:
- Contract tests and parity tests are mandatory for each migrated domain.
- Any intentional API changes are out of scope and must be separate work.

## Decision 7: Feature-toggle strategy

Decision:
- Use per-domain runtime toggles to switch between legacy and ORM-backed implementations during rollout.

Rationale:
- Enables safe fallback and incremental deployment.

Implications:
- Toggle defaults stay conservative until each domain proves parity.

## Non-goals (Locked)

- No API surface redesign in this migration.
- No PostgreSQL feature expansion in this migration.
- No broad refactors outside persistence migration boundaries.

## Validation requirements from these decisions

1. Fresh database path:
- upgrade to head builds each target schema successfully.

2. Existing database path:
- stamp baseline then upgrade succeeds without data loss.

3. Parity checks:
- legacy vs ORM outputs match for auth, audit, chat sessions, orchestration.

4. Contract checks:
- jobs, audit, auth, and chat session route responses remain stable.
