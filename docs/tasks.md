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

## Phase 2 — Redis Layer

- [ ] #10 Implement `app/redis/client.py` — async Redis connection + FastAPI dependency
- [ ] #11 Implement `app/redis/idmap.py` — ID mapping CRUD: write `scim↔target↔external` (no TTL); lookup by `scim_id` or `external_id`; delete on resource removal
- [ ] #12 Implement `app/redis/cache.py` — Brivo response cache: read/write/invalidate for user, group, and group-member responses (TTL 5 min)
- [ ] #13 Implement `app/redis/locks.py` — `SET NX EX 300` idempotency lock for create sagas; delete on completion or rollback

## Phase 3 — Pydantic Models

- [ ] #14 Implement `app/models/user.py` — SCIM User schemas
- [ ] #15 Implement `app/models/group.py` — SCIM Group schemas (displayName ≤ 35 chars)
- [ ] #16 Implement `app/models/common.py` — ListResponse, PatchOp, Error, Meta
- [ ] #17 Implement `app/models/brivo.py` — Brivo User, Group, paginated list

## Phase 4 — Mock Brivo Service

- [ ] #18 Mock Brivo skeleton — FastAPI app, `/health`, in-memory store
- [ ] #19 Mock Brivo user endpoints — list, create, get, update, delete, list groups
- [ ] #20 Mock Brivo group endpoints + member management
- [ ] #21 Mock Brivo behavior simulation — latency, error rate, partial responses, 429

## Phase 5 — Brivo Client

- [ ] #22 Implement `app/brivo/client.py` — httpx wrapper for all Brivo endpoints
- [ ] #23 Implement `app/brivo/rate_limiter.py` — aiolimiter + tenacity 429 handling

## Phase 6 — Field Mapper

- [ ] #24 Implement `app/services/field_mapper.py` — write path (SCIM→Brivo)
- [ ] #25 Implement `app/services/field_mapper.py` — read path (Brivo→SCIM) + meta computation (timestamps from idmap `created_at`; version hash from Brivo resource JSON)
- [ ] #26 Implement member hydration — resolve Brivo user IDs → scim_ids via idmap

## Phase 7 — Saga Orchestrator

- [ ] #27 Implement `app/services/saga.py` — base saga runner (state machine, tenacity, rollback)
- [ ] #28 Implement Create User saga — step 0: SETNX lock (409 on conflict); step 1: POST to Brivo; step 2: write idmap keys (no TTL), DEL lock
- [ ] #29 Implement Delete User saga — fetch group memberships from Brivo, remove from each group, DELETE from Brivo, DEL idmap + cache keys
- [ ] #30 Implement Create Group saga — step 0: SETNX lock; step 1: POST to Brivo; step 2: write idmap; step 3: bulk add members (resolve scim→target via idmap upfront)
- [ ] #31 Implement Delete Group saga
- [ ] #32 Implement Add Member(s) saga (PATCH `add`) — resolve all scim→target IDs from idmap upfront (400 if any missing), PUT each to Brivo, invalidate member cache
- [ ] #33 Implement Remove Member saga (PATCH `remove`)
- [ ] #34 Implement Update Group saga (PUT) — fetch current members from Brivo (cache), resolve new members from idmap, add new (PUT to Brivo), remove stale (DELETE from Brivo), invalidate cache
- [ ] #35 Implement Update User read-modify-write (no saga) — fetch from Brivo (cache), merge PUT/PATCH replace fields, PUT to Brivo (tenacity), invalidate cache, return Brivo→SCIM mapped response

## Phase 8 — SCIM Routers

- [ ] #36 Implement `app/routers/users.py` — all 6 user endpoints
- [ ] #37 Implement `app/routers/groups.py` — all 6 group endpoints; PATCH `replace` group attributes handled inline (no saga): PUT to Brivo + invalidate cache, tenacity retries
- [ ] #38 Implement `app/routers/discovery.py` — unauthenticated discovery endpoints
- [ ] #39 Implement `main.py` — app assembly, middleware, lifespan
