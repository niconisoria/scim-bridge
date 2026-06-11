# Redis Integration

Redis serves as a **cache** for hot integration ID lookups backed by PostgreSQL. DB is always the source of truth.

ID mappings and saga state are owned by PostgreSQL — see [database.md](database.md).

## Cache Effectiveness

Two cache key types serve different access patterns:

| Key type | Used by | Repetition | Value |
|---|---|---|---|
| `cache:ext` (`external_id` → `scim_id`) | GET /Groups list — member hydration; GET /Users list — Brivo→SCIM resolution | N groups × M members per request; same users appear across multiple groups | **High** — hot keys hit many times per list request |
| `cache:scim` (`scim_id` → `target_id`) | Create Group saga (member resolution); PATCH add/remove member | N members per create; 1 per PATCH | Medium — saves DB round-trip per member on bulk creates |

Single-resource GETs (`GET /Users/{id}`, `GET /Groups/{id}`) also hit `cache:scim` but at low repetition — DB would be fast enough, cache is a low-cost bonus.

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
| Get resource by `scim_id` | Read `cache:{target}:scim:{type}:{scim_id}` (miss → query DB, populate cache) |
| Get resource by `external_id` | Read `cache:{target}:ext:{type}:{external_id}` (miss → query DB, populate cache) |
| Create resource (saga complete) | Populate both cache keys |
| Delete resource | DEL both cache keys |
