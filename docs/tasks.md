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
- [ ] #9 Implement `app/core/errors.py` — SCIM error builder

## Phase 2 — Database Layer

- [ ] #10 Alembic init — `alembic/env.py`, `alembic.ini`, async SQLAlchemy engine
- [ ] #11 Implement `app/db/models.py` — SQLAlchemy ORM models: `integrations`, `provisioning_actions`
- [ ] #12 Write initial Alembic migration — create both tables with indexes/constraints
- [ ] #13 Implement `app/db/session.py` — async session factory + FastAPI dependency
- [ ] #14 Implement `app/db/repositories/integrations.py` — CRUD: insert pending, activate, lookup by scim_id/external_id/target_id, delete
- [ ] #15 Implement `app/db/repositories/saga_store.py` — CRUD: create saga, update step, set terminal status
- [ ] #16 Implement startup task — mark stale `running` sagas `failed`, delete orphaned `pending` integration rows

## Phase 3 — Redis Cache Layer

- [ ] #17 Implement `app/redis/cache.py` — cache-aside reads/writes/invalidation for integration lookups

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
- [ ] #28 Implement `app/brivo/rate_limiter.py` — aiolimiter + Redis coordination + tenacity 429

## Phase 7 — Field Mapper

- [ ] #29 Implement `app/services/field_mapper.py` — write path (SCIM→Brivo)
- [ ] #30 Implement `app/services/field_mapper.py` — read path (Brivo→SCIM) + meta computation
- [ ] #31 Implement member hydration in `field_mapper.py`

## Phase 8 — Saga Orchestrator

- [ ] #32 Implement `app/services/saga.py` — base saga runner (state machine, tenacity, rollback)
- [ ] #33 Implement Create User saga
- [ ] #34 Implement Delete User saga
- [ ] #35 Implement Create Group saga (with members)
- [ ] #36 Implement Delete Group saga
- [ ] #37 Implement Add Member and Remove Member sagas

## Phase 9 — SCIM Routers

- [ ] #38 Implement `app/routers/users.py` — all 6 user endpoints
- [ ] #39 Implement `app/routers/groups.py` — all 6 group endpoints
- [ ] #40 Implement `app/routers/discovery.py` — unauthenticated discovery endpoints
- [ ] #41 Implement `main.py` — app assembly, middleware, lifespan
