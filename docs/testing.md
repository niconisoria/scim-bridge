# Testing Strategy

## Tools

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Async test runner (`asyncio_mode = "auto"`) |
| `httpx.AsyncClient` | SCIM endpoint calls in tests |
| `fakeredis` | In-memory Redis for idmap + cache tests (no Docker) |
| `respx` | Mock `httpx` calls to Brivo |

## Unit Tests (`tests/unit/`)

Each component tested in isolation. Redis replaced by `fakeredis`. Brivo calls mocked with `respx`.

| Component | What to test |
|---|---|
| SCIM schemas | Validation, serialization, PATCH op parsing |
| Auth middleware | Valid token passes; missing/invalid returns `401` |
| ID mapping (idmap) | Write scim↔target↔external; lookup by `scim_id`; lookup by `external_id`; delete; missing key returns `None` |
| Brivo cache layer | Cache-aside read hit/miss; TTL set correctly; invalidation on write/delete |
| Idempotency lock | SETNX succeeds on first call; fails on second (returns None); DEL releases lock |
| Rate limiter | Token acquisition (aiolimiter leaky bucket, in-process); backoff on `429` |
| Saga orchestrator | Forward happy path; rollback on step failure; unrecoverable step handling |
| Field mapper | SCIM→Brivo (write path) and Brivo→SCIM (read path) translation, including missing optional fields |

## Integration Tests (`tests/integration/`)

Full stack: real Redis (Docker), SCIM bridge, `respx`-mocked Brivo.

| Scenario | What to verify |
|---|---|
| Create user end-to-end | `201`, idmap keys written (permanent), lock DEL'd, Brivo called once |
| Delete user end-to-end | Brivo DELETE called, idmap + cache keys DEL'd |
| Create group with members | Group created in Brivo, idmap written, members added in Brivo, member cache invalidated |
| Saga rollback on Brivo failure | Partial state reversed, idmap keys DEL'd if written, lock DEL'd |
| PATCH add/remove member | Correct Brivo member call, member cache invalidated, scim_id resolved from idmap |
| Rate limit queuing | 25 concurrent requests complete, none dropped |
| Auth rejection | `401` on missing and wrong token |
| Write-path partial Brivo response | Brivo create returns user without `phoneNumbers` → bridge stores what the SCIM request contained, no error |
| Create idempotency | Duplicate `POST /Users` same `externalId` → `409` (SETNX fails), no second Brivo call |
| Concurrent create race | Two simultaneous `POST /Users` same `externalId` → exactly one `201`, one `409` |
| Read path — cache hit | `GET /Users/{id}` returns data from Redis cache; respx asserts zero Brivo calls |
| Read path — cache miss | `GET /Users/{id}` with empty cache → Brivo called once, response cached |
| Pagination — Brivo proxy | `GET /Users?startIndex=2&count=5` → Brivo called with offset=1, pageSize=5 |
| Filter — externalId | `filter=externalId eq "x"` → idmap lookup, then Brivo cache/call; no full-scan |
| Filter — userName case-insensitive | `filter=userName eq "JOHN@EXAMPLE.COM"` matches Brivo user with lowercase email |
| PATCH path filter parsing | `members[value eq "abc"]` parsed correctly; malformed path → `400` |
| PATCH pathless replace | `PATCH /Groups/{id}` with `{op:replace, value:{displayName:"..."}}` (no path) → group updated |
| PATCH replace members | `PATCH /Groups/{id}` with `{op:replace, path:members, value:[...]}` → full membership diff applied |
| PUT clears nullable fields | `PUT /Users/{id}` without `phoneNumbers` → Brivo called without `phoneNumbers` |
| `displayName` > 35 chars | `POST /Groups` with 36-char name → `400` before any Brivo call |
| Member not provisioned | Create group with member `scim_id` not in idmap → `400`, no Brivo calls made |
| Ordering stability | `GET /Users` page 1 + page 2 return distinct non-overlapping users in consistent order |
