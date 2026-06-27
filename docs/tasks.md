# Tasks

## Phase 0 — Scaffolding

- [x] #1 Create project directory structure — `app/`, `tests/`, `docs/specs/`, all `__init__.py`
- [x] #2 Create `pyproject.toml` with all dependencies
- [x] #3 Create `.env.example`
- [x] #4 Create `Dockerfile` and `Dockerfile.brivo`
- [x] #5 Create `docker-compose.yml`

## Phase 1 — Core

- [x] #6 Implement `app/core/config.py` — pydantic-settings
- [x] #7 Implement `app/core/logging.py` — structlog JSON + correlation_id
- [x] #8 Implement `app/core/auth.py` — bearer token middleware
- [x] #9 Implement `app/core/errors.py` — SCIM error builder (`status` field as string per RFC 7644 §3.12)

## Phase 2 — Redis Layer

- [x] #10 Implement `app/redis/store.py` — async Redis connection + FastAPI dependency; ID mapping CRUD (`scim↔target↔external↔tid`, no TTL); Brivo response cache (TTL 5 min); `SET NX EX 300` idempotency locks

## Phase 3 — Pydantic Models

- [x] #11 Implement `app/models/user.py` — SCIM User schemas
- [x] #12 Implement `app/models/group.py` — SCIM Group schemas (displayName ≤ 35 chars)
- [x] #13 Implement `app/models/common.py` — ListResponse, PatchOp, Error, Meta
- [x] #14 Implement `app/models/brivo.py` — Brivo User, Group, paginated list (used by bridge only — mock Brivo defines its own inline schemas)

## Phase 4 — Mock Brivo Service

Mock is a standalone FastAPI app (`Dockerfile.brivo`) with its own inline Pydantic schemas — it does **not** import from `app/`. Independently testable with curl after this phase.

- [x] #15 Mock Brivo skeleton — FastAPI app, `/health`, in-memory store, inline schemas
- [x] #16 Mock Brivo user endpoints — list, create, get, update, delete, list user's groups
- [x] #17 Mock Brivo group endpoints + member management
- [x] #18 Mock Brivo behavior simulation — latency, error rate, partial responses, 429

## Phase 5 — Brivo Client

- [x] #19 Implement `app/brivo/client.py` — httpx wrapper for all Brivo endpoints
- [x] #20 Implement `app/brivo/rate_limiter.py` — aiolimiter + tenacity 429 handling

## Phase 6 — Field Mapper

- [x] #21 Implement `app/services/field_mapper.py` — write path (SCIM→Brivo)
- [x] #22 Extend `app/services/field_mapper.py` — read path (Brivo→SCIM) + meta computation (timestamps from idmap `created_at` and Brivo `updated`; version hash from Brivo resource JSON)
- [x] #23 Extend `app/services/field_mapper.py` — member hydration: resolve Brivo `target_id` → `scim_id` via `idmap:tid` keys

## Phase 7 — Saga Orchestrator

- [x] #24 Implement `app/services/saga.py` — base saga runner (state machine, rollback); all following saga tasks depend on this
- [x] #25 Implement Create User saga — step 0: SETNX lock (409 on conflict); step 1: POST to Brivo; step 2: write idmap keys (no TTL), DEL lock
- [x] #26 Implement Delete User saga — `GET /users/{id}/groups`, remove from each group, DELETE from Brivo, DEL idmap + cache keys
- [x] #27 Implement Create Group saga — step 0: SETNX lock; step 1: POST to Brivo; step 2: write idmap; step 3: bulk add members (resolve scim→target via idmap upfront)
- [x] #28 Implement Delete Group saga
- [x] #29 Implement Add Member(s) saga (PATCH `add`) — resolve all scim→target IDs from idmap upfront (400 if any missing), PUT each to Brivo, invalidate member cache
- [x] #30 Implement Remove Member saga (PATCH `remove`)
- [x] #31 Implement Update Group saga (PUT) — fetch current members from Brivo (cache), resolve new members from idmap, add new (PUT to Brivo), remove stale (DELETE from Brivo), invalidate cache
- [x] #32 Implement Update User read-modify-write (no saga) — fetch from Brivo (cache), merge PUT/PATCH replace fields, PUT to Brivo (tenacity), invalidate cache, return Brivo→SCIM mapped response

## Phase 8 — SCIM Routers

- [x] #33 Implement `app/routers/users.py` — all 6 user endpoints
- [x] #34 Implement `app/routers/groups.py` — all 6 group endpoints; PATCH `replace` group attributes handled inline (no saga): PUT to Brivo + invalidate cache, tenacity retries
- [x] #35 Implement `app/routers/discovery.py` — unauthenticated discovery endpoints
- [ ] #36 Implement `main.py` — app assembly, middleware, lifespan
