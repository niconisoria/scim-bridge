# Testing Strategy

## Tools

| Tool | Purpose |
|---|---|
| `pytest` + `pytest-asyncio` | Async test runner (`asyncio_mode = "auto"`) |
| `httpx.AsyncClient` | SCIM endpoint calls in tests |
| `pytest-postgresql` | Ephemeral PostgreSQL for unit + integration tests |
| `fakeredis` | In-memory Redis for cache + rate-limiter tests (no Docker) |
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
| Rate limiter | Token acquisition; Redis window counter; backoff on `429` |
| Saga orchestrator | Forward happy path; rollback on step failure; unrecoverable step handling |
| Field mapper | SCIM→Brivo and Brivo→SCIM translation, including missing optional fields |

## Integration Tests (`tests/integration/`)

Full stack: real PostgreSQL (Docker), real Redis (Docker), SCIM bridge, `respx`-mocked Brivo.

| Scenario | What to verify |
|---|---|
| Create user end-to-end | `201`, DB integration row written (active), cache populated, correct Brivo call made |
| Delete user end-to-end | Brivo DELETE called, DB integration row deleted, cache invalidated |
| Create group with members | Group created, members added in order |
| Saga rollback on Brivo failure | Partial state reversed, DB integration row deleted, cache invalidated |
| PATCH add/remove member | Correct Brivo member call, ID resolved from DB/cache |
| Rate limit queuing | 25 concurrent requests complete, none dropped |
| Auth rejection | `401` on missing and wrong token |
| Partial Brivo response | Bridge handles missing optional fields without error |
| Create idempotency — DB hit | Duplicate `POST /Users` same `externalId` → `409`, no second Brivo call |
| Create idempotency — Brivo fallback | DB miss, Brivo has user with `externalId` → `409`, integration row rebuilt |
| Concurrent create race | Two simultaneous `POST /Users` same `externalId` → exactly one `201`, one `409` |
| Self-healing stale mapping | Brivo returns `404` for mapped resource → DB row deleted, cache invalidated, `404` returned to caller |
| Pagination translation | `startIndex=2&count=5` → Brivo called with `offset=1&pageSize=5` |
| Filter in memory | `filter=userName eq "x"` → all Brivo users fetched, correct user returned |
| PATCH path filter parsing | `members[value eq "abc"]` parsed correctly; malformed path → `400` |
| PUT clears nullable fields | `PUT /Users/{id}` without `phoneNumbers` → Brivo called with empty `phoneNumbers` |
| `displayName` > 35 chars | `POST /Groups` with 36-char name → `400` before any Brivo call |
| Member not provisioned | Create group with member `scim_id` not in DB → `400`, no Brivo calls made |
