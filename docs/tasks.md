# Tasks

## Phase 0 — Scaffolding

- [ ] #1 Create project directory structure — `app/`, `tests/`, `docs/specs/`, all `__init__.py`
- [ ] #2 Create `pyproject.toml` with all dependencies
- [ ] #3 Create `.env.example`
- [ ] #4 Create `Dockerfile` and `Dockerfile.brivo`
- [ ] #5 Create `docker-compose.yml`

## Phase 1 — Core

- [ ] #6 Implement `app/core/config.py` — pydantic-settings
- [ ] #7 Implement `app/core/logging.py` — structlog JSON + correlation_id
- [ ] #8 Implement `app/core/auth.py` — bearer token middleware
- [ ] #9 Implement `app/core/errors.py` — SCIM error builder (`status` field as string per RFC 7644 §3.12)

## Phase 2 — Database Layer

- [ ] #10 Alembic init — `alembic/env.py`, `alembic.ini`, async SQLAlchemy engine
- [ ] #11 Implement `app/db/models.py` — SQLAlchemy ORM models: `integrations`, `users`, `groups`, `group_members`, `provisioning_actions`
- [ ] #12 Write initial Alembic migration — create all five tables with indexes/constraints
- [ ] #13 Implement `app/db/session.py` — async session factory + FastAPI dependency
- [ ] #14 Implement `app/db/repositories/integrations.py` — CRUD: insert pending, activate, lookup by scim_id/external_id/target_id, delete
- [ ] #15 Implement `app/db/repositories/resources.py` — user CRUD (insert, update attributes, delete); group CRUD; `group_members` insert/delete/list
- [ ] #16 Implement `app/db/repositories/saga_store.py` — CRUD: create saga, update step, set terminal status
- [ ] #17 Implement startup task — mark stale `running` provisioning_actions as `failed`; do NOT delete `pending` integration rows (they act as tombstones, preventing duplicate creation on IdP retry)

## Phase 3 — Redis Cache Layer

- [ ] #18 Implement `app/redis/cache.py` — cache-aside reads/writes/invalidation for integration lookups

## Phase 4 — Pydantic Models

- [ ] #19 Implement `app/models/user.py` — SCIM User schemas
- [ ] #20 Implement `app/models/group.py` — SCIM Group schemas (displayName ≤ 35 chars)
- [ ] #21 Implement `app/models/common.py` — ListResponse, PatchOp, Error, Meta
- [ ] #22 Implement `app/models/brivo.py` — Brivo User, Group, paginated list

## Phase 5 — Mock Brivo Service

- [ ] #23 Mock Brivo skeleton — FastAPI app, `/health`, in-memory store
- [ ] #24 Mock Brivo user endpoints — list, create, get, update, delete, list groups
- [ ] #25 Mock Brivo group endpoints + member management
- [ ] #26 Mock Brivo behavior simulation — latency, error rate, partial responses, 429

## Phase 6 — Brivo Client

- [ ] #27 Implement `app/brivo/client.py` — httpx wrapper for all Brivo endpoints
- [ ] #28 Implement `app/brivo/rate_limiter.py` — aiolimiter + tenacity 429 handling

## Phase 7 — Field Mapper

- [ ] #29 Implement `app/services/field_mapper.py` — write path (SCIM→Brivo)
- [ ] #30 Implement `app/services/field_mapper.py` — read path (Brivo→SCIM) + meta computation
- [ ] #31 Implement member hydration in `field_mapper.py`

## Phase 8 — Saga Orchestrator

- [ ] #32 Implement `app/services/saga.py` — base saga runner (state machine, tenacity, rollback)
- [ ] #33 Implement Create User saga — step 0: dual-write to `integrations` (pending) + `users`; step 1: POST to Brivo; step 2: activate integration + populate cache
- [ ] #34 Implement Delete User saga — save group memberships, remove from each group (Brivo then `group_members`), DELETE from Brivo, DELETE from `users` + `integrations`, invalidate cache
- [ ] #35 Implement Create Group saga — step 0: dual-write to `integrations` (pending) + `groups`; step 1: POST to Brivo; step 2: activate + populate cache; step 3: bulk add members
- [ ] #36 Implement Delete Group saga
- [ ] #37 Implement Add Member(s) saga (PATCH `add`) — resolve all scim→target IDs upfront (400 if any missing), PUT each to Brivo + INSERT into `group_members`; track added_members in saga JSONB for rollback
- [ ] #38 Implement Remove Member saga (PATCH `remove`)
- [ ] #39 Implement Update Group saga (PUT) — full member diff: save current members, resolve new members, add new (PUT to Brivo + INSERT into `group_members`), remove stale (DELETE from Brivo + `group_members`)
- [ ] #40 Implement Update User read-modify-write (no saga) — SELECT from DB, merge PUT/PATCH replace fields, PUT to Brivo (tenacity), UPDATE `users` table, return full SCIM resource from DB

## Phase 9 — SCIM Routers

- [ ] #41 Implement `app/routers/users.py` — all 6 user endpoints
- [ ] #42 Implement `app/routers/groups.py` — all 6 group endpoints; PATCH `replace` group attributes handled inline (no saga): PUT to Brivo + UPDATE `groups`, tenacity retries
- [ ] #43 Implement `app/routers/discovery.py` — unauthenticated discovery endpoints
- [ ] #44 Implement `main.py` — app assembly, middleware, lifespan

## Phase 10 — Reconciliation Job

- [ ] #45 Implement reconcile job (`app/services/reconcile.py`) — paginate all active resources from DB; GET each from Brivo; on 404: delete from `users`/`groups`/`group_members`/`integrations`, invalidate cache; on attribute diff: UPDATE in DB; reconcile `group_members` against Brivo member lists; runs on configurable schedule using same rate limiter as write path
