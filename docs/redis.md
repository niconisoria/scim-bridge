# Redis Integration

Single Redis instance. Three concerns: ID mapping (persistent store), saga state, rate-limiter coordination.

> **Redis is the persistent store for ID mappings** — not a cache. `scim_id` is bridge-generated and unknown to Brivo or Okta, so there is no external source of truth to reconstruct it from. AOF persistence must be enabled. Data loss = full re-sync required.

## Key Inventory

### ID Mapping

| Key | Type | Value | TTL |
|---|---|---|---|
| `scim:user:{scim_id}` | string | JSON `{ brivo_id, external_id }` | none |
| `ext:user:{external_id}` | string | `scim_id` | none |
| `scim:group:{scim_id}` | string | JSON `{ brivo_id, external_id }` | none |
| `ext:group:{external_id}` | string | `scim_id` | none |

No TTL — invalidated explicitly on resource delete.

`scim:user:{scim_id}` stores `external_id` in the value so the delete saga can clean up both keys without an extra Brivo call.

`ext:user:{external_id}` serves two purposes:
1. **Create idempotency** — check before creating; if found, user already provisioned.
2. **List mapping** — Brivo list responses carry `externalId`; use this key to resolve `scim_id`.

### Saga State

| Key | Type | Value | TTL |
|---|---|---|---|
| `saga:{saga_id}` | hash | `status`, `steps` (JSON array), `current_step`, `created_at` | 24h after terminal state |

State written **before** first forward step executes. `steps` array records each step's state and any rollback data needed (e.g., `brivo_id` created mid-saga).

### Rate Limiter

| Key | Type | Value | TTL |
|---|---|---|---|
| `ratelimit:brivo:window:{unix_second}` | string | integer request count | 2s |

See [rate-limiter.md](rate-limiter.md) for usage pattern.

## Invalidation Rules

| Key pattern | Invalidated by |
|---|---|
| `scim:user:{scim_id}` | Delete user saga step 4 (explicit `DEL`) |
| `ext:user:{external_id}` | Delete user saga step 4 (explicit `DEL`) |
| `scim:group:{scim_id}` | Delete group saga |
| `ext:group:{external_id}` | Delete group saga |
| `saga:{saga_id}` | TTL auto-expires 24h after terminal state |
| `ratelimit:brivo:window:{ts}` | TTL auto-expires after 2s |

## Self-Healing on Brivo 404

If a Brivo call returns `404` for a resource that has a Redis mapping, the mapping is stale (Brivo mutated out-of-band). Bridge must:

1. Delete `scim:user:{scim_id}` and `ext:user:{external_id}` (read `external_id` from the value first)
2. Return `404` to caller

## Concurrent Create Race Condition

Two simultaneous `POST /Users` (or `POST /Groups`) with the same `externalId` can both miss Redis and Brivo checks, then both proceed to create — producing a duplicate Brivo resource.

Prevention: use Redis atomic `SET NX` (set if not exists) on the external-ID key as a distributed lock during the create flow.

### Users
```
SET ext:user:{external_id} "pending" NX EX 30
```

### Groups
```
SET ext:group:{external_id} "pending" NX EX 30
```

In both cases:
- If `SET NX` succeeds → this process owns the create, proceed
- If `SET NX` fails → another process is creating the same resource, return `409`
- On saga completion: overwrite with actual `scim_id` (no TTL)
- On saga failure/rollback: delete the key

The 30s TTL on the `"pending"` value is a safety net — if the bridge crashes mid-create, the lock auto-expires and Okta can retry.

## Create Idempotency (Pre-check)

Before every `POST /Users` or `POST /Groups`:

1. Check `ext:user:{external_id}` — if found, user already provisioned → return `409` with existing `scim_id`
2. If miss — query Brivo: `GET /v1/api/users?externalId={external_id}`
3. If Brivo finds it — rebuild Redis mapping, return `409`
4. If not found anywhere — proceed with create saga

Step 2 guards against the case where Redis mapping was lost (crash between saga steps) but Brivo state persists.

## Access Patterns

| Operation | Keys touched |
|---|---|
| Create user | Check `ext:user:*`; write `scim:user:*` + `ext:user:*`; write `saga:*` |
| Delete user | Read `scim:user:*` (get `external_id`); delete `scim:user:*` + `ext:user:*`; write `saga:*` |
| Create group | Check `ext:group:*`; write `scim:group:*` + `ext:group:*`; write `saga:*` |
| Delete group | Read `scim:group:*`; delete `scim:group:*` + `ext:group:*`; write `saga:*` |
| PATCH add/remove member | Read `scim:user:*` (ID resolution); write `saga:*` |
| GET user / group | Read `scim:user:*` or `scim:group:*` |
| GET /Users list | Read `ext:user:*` per Brivo result (resolve `scim_id`) |
| Brivo call | INCR + EXPIRE `ratelimit:brivo:window:*` |
