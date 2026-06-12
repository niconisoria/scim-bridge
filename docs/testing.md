# Testing Strategy

## Tools

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Async test runner (`asyncio_mode = "auto"`) |
| `httpx.AsyncClient` | SCIM endpoint calls in tests |
| `pytest-postgresql` | Ephemeral PostgreSQL for unit + integration tests |
| `fakeredis` | In-memory Redis for cache tests (no Docker) |
| `respx` | Mock `httpx` calls to Brivo |

## Unit Tests (`tests/unit/`)

Each component tested in isolation. DB replaced by ephemeral PostgreSQL fixture. Redis replaced by `fakeredis`. Brivo calls mocked with `respx`.

| Component | What to test |
|---|---|
| SCIM schemas | Validation, serialization, PATCH op parsing |
| Auth middleware | Valid token passes; missing/invalid returns `401` |
| Integrations repository | Insert pending, activate, lookup by scim_id/external_id/target_id, delete; missing ID returns `None` |
| Saga repository | Create saga, update step, set terminal status |
| Cache layer | Cache-aside read hit/miss; invalidation on delete |
| Rate limiter | Token acquisition (aiolimiter leaky bucket, in-process); backoff on `429` |
| Saga orchestrator | Forward happy path; rollback on step failure; unrecoverable step handling |
| Field mapper | SCIM→Brivo (write path) and DB→SCIM (read path) translation, including missing optional fields |

## Integration Tests (`tests/integration/`)

Full stack: real PostgreSQL (Docker), real Redis (Docker), SCIM bridge, `respx`-mocked Brivo.

| Scenario | What to verify |
|---|---|
| Create user end-to-end | `201`, `users` + `integrations` rows written (active), cache populated, Brivo called |
| Delete user end-to-end | Brivo DELETE called, `users` + `integrations` + `group_members` rows deleted, cache invalidated |
| Create group with members | Group created in Brivo + DB, members added in Brivo + `group_members` table in order |
| Saga rollback on Brivo failure | Partial state reversed, DB rows deleted, cache invalidated |
| PATCH add/remove member | Correct Brivo member call, `group_members` table updated, ID resolved from DB/cache |
| Rate limit queuing | 25 concurrent requests complete, none dropped |
| Auth rejection | `401` on missing and wrong token |
| Write-path partial Brivo response | Brivo create returns user without `phoneNumbers` → bridge stores what Brivo returns, no error |
| Create idempotency | Duplicate `POST /Users` same `externalId` → `409` (UNIQUE constraint on `integrations`), no second Brivo call |
| Concurrent create race | Two simultaneous `POST /Users` same `externalId` → exactly one `201`, one `409` |
| Self-healing stale mapping (write) | Saga Brivo call returns `404` → `users`/`integrations` rows deleted, cache invalidated, `404` returned to caller |
| Pagination — DB query | `GET /Users?startIndex=2&count=5` → DB queried with `OFFSET=1 LIMIT=5`; no Brivo call |
| Filter — DB index scan | `GET /Users?filter=userName eq "x"` → `SELECT ... WHERE username='x'`; no Brivo call |
| Filter — case insensitive | `filter=userName eq "JOHN@EXAMPLE.COM"` matches lowercase-stored username |
| Read path — no Brivo call | `GET /Users/{id}` returns data from bridge DB; respx asserts zero Brivo calls |
| PATCH path filter parsing | `members[value eq "abc"]` parsed correctly; malformed path → `400` |
| PATCH pathless replace | `PATCH /Groups/{id}` with `{op:replace, value:{displayName:"..."}}` (no path) → group updated |
| PATCH replace members | `PATCH /Groups/{id}` with `{op:replace, path:members, value:[...]}` → full membership diff applied |
| PUT clears nullable fields | `PUT /Users/{id}` without `phoneNumbers` → Brivo called without `phoneNumbers`; DB `phone` set null |
| `displayName` > 35 chars | `POST /Groups` with 36-char name → `400` before any Brivo call |
| Member not provisioned | Create group with member `scim_id` not in DB → `400`, no Brivo calls made |
| Ordering stability | `GET /Users` page 1 + page 2 return distinct non-overlapping users in consistent `created_at ASC` order |
