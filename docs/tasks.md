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

## Phase 2 — Redis Layer

- [ ] #10 Implement `app/redis/id_mapper.py` — ID mapping CRUD + SET NX lock
- [ ] #11 Implement `app/redis/saga_store.py` — saga state hash
- [ ] #12 Implement `app/redis/rate_window.py` — sliding window counter

## Phase 3 — Pydantic Models

- [ ] #13 Implement `app/models/user.py` — SCIM User schemas
- [ ] #14 Implement `app/models/group.py` — SCIM Group schemas (displayName ≤ 35 chars)
- [ ] #15 Implement `app/models/common.py` — ListResponse, PatchOp, Error, Meta
- [ ] #16 Implement `app/models/brivo.py` — Brivo User, Group, paginated list

## Phase 4 — Mock Brivo Service

- [ ] #17 Mock Brivo skeleton — FastAPI app, `/health`, in-memory store
- [ ] #18 Mock Brivo user endpoints — list, create, get, update, delete, list groups
- [ ] #19 Mock Brivo group endpoints + member management
- [ ] #20 Mock Brivo behavior simulation — latency, error rate, partial responses, 429

## Phase 5 — Brivo Client

- [ ] #21 Implement `app/brivo/client.py` — httpx wrapper for all Brivo endpoints
- [ ] #22 Implement `app/brivo/rate_limiter.py` — aiolimiter + Redis coordination + tenacity 429

## Phase 6 — Field Mapper

- [ ] #23 Implement `app/services/field_mapper.py` — write path (SCIM→Brivo)
- [ ] #24 Implement `app/services/field_mapper.py` — read path (Brivo→SCIM) + meta computation
- [ ] #25 Implement member hydration in field_mapper.py

## Phase 7 — Saga Orchestrator

- [ ] #26 Implement `app/services/saga.py` — base saga runner (state machine, tenacity, rollback)
- [ ] #27 Implement Create User saga
- [ ] #28 Implement Delete User saga
- [ ] #29 Implement Create Group saga (with members + SET NX lock)
- [ ] #30 Implement Delete Group saga
- [ ] #31 Implement Add Member and Remove Member sagas

## Phase 8 — SCIM Routers

- [ ] #32 Implement `app/routers/users.py` — all 6 user endpoints
- [ ] #33 Implement `app/routers/groups.py` — all 6 group endpoints
- [ ] #34 Implement `app/routers/discovery.py` — unauthenticated discovery endpoints
- [ ] #35 Implement `main.py` — app assembly, middleware, lifespan
