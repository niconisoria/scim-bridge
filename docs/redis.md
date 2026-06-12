# Redis Integration

Redis serves as a **cache** for hot DB lookups backed by PostgreSQL. DB is always the source of truth — Redis is read-through only.

Resource state, ID mappings, and saga state are owned by PostgreSQL — see [database.md](database.md).

## Cache Effectiveness

Two cache key types serve different access patterns:

| Key type | Used by | Repetition | Value |
|---|---|---|---|
| `cache:ext` (`external_id` → `scim_id`) | `externalId eq` filter; saga idempotency lookups | Low-medium | Low — DB index scan is fast enough; cache is a low-cost bonus |
| `cache:scim` (`scim_id` → `target_id`) | Write path: all sagas that call Brivo with a `target_id`; PATCH add/remove member; Update User/Group | N members per bulk create; 1 per PATCH | **High** — every Brivo write needs `target_id`; cache avoids repeated DB hits on bulk ops |

Single-resource GETs (`GET /Users/{id}`, `GET /Groups/{id}`) read from bridge DB directly — no `target_id` needed on the read path, so cache is not consulted for reads.

## Key Inventory

| Key | Type | Value | TTL |
|---|---|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | string | JSON `{ target_id, external_id }` | 5 min |
| `cache:{target}:ext:{type}:{external_id}` | string | JSON `{ scim_id, target_id }` | 5 min |

`type` is `user` or `group`. `target` is the downstream system identifier (e.g. `brivo`).

**Cache-aside pattern:** read Redis first; on miss query DB, populate cache. Invalidated explicitly on resource delete.

## Invalidation Rules

| Key pattern | Invalidated by |
|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | Delete saga step 4 (explicit DEL) |
| `cache:{target}:ext:{type}:{external_id}` | Delete saga step 4 (explicit DEL) |

TTL is a safety net — explicit invalidation keeps cache consistent without waiting for expiry.

## Self-Healing on Target 404

If a target API call returns `404` for a resource that has a DB mapping, the mapping is stale (target mutated out-of-band). Bridge must:

1. DELETE the `integrations` row from DB
2. DEL both cache keys from Redis
3. Return `404` to caller

## Access Patterns

| Operation | Redis keys touched |
|---|---|
| Resolve `scim_id → target_id` (write path) | Read `cache:{target}:scim:{type}:{scim_id}` (miss → query DB, populate cache) |
| Resolve `external_id → scim_id` (filter/saga) | Read `cache:{target}:ext:{type}:{external_id}` (miss → query DB, populate cache) |
| Create resource (saga complete) | Populate both cache keys |
| Delete resource | DEL both cache keys |
| Read resource (GET /Users/{id}, GET /Groups/{id}) | Not cached — served directly from bridge DB |
