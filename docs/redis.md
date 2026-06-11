# Redis Integration

Redis serves two concerns: **cache** (hot ID lookups backed by PostgreSQL) and **rate-limiter coordination** (sliding window counter).

ID mappings and saga state are owned by PostgreSQL — see [database.md](database.md).

## Key Inventory

### Cache Layer

| Key | Type | Value | TTL |
|---|---|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | string | JSON `{ target_id, external_id }` | 5 min |
| `cache:{target}:ext:{type}:{external_id}` | string | JSON `{ scim_id, target_id }` | 5 min |

`type` is `user` or `group`. `target` is the downstream system identifier (e.g. `brivo`).

Cache-aside pattern: read Redis first; on miss query DB, then write to cache. Invalidated explicitly on resource delete.

### Rate Limiter

| Key | Type | Value | TTL |
|---|---|---|---|
| `ratelimit:{target}:window:{unix_second}` | string | integer request count | 2s |

See [rate-limiter.md](rate-limiter.md) for usage pattern.

## Invalidation Rules

| Key pattern | Invalidated by |
|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | Delete saga (explicit DEL) |
| `cache:{target}:ext:{type}:{external_id}` | Delete saga (explicit DEL) |
| `ratelimit:{target}:window:{ts}` | TTL auto-expires after 2s |

## Self-Healing on Target 404

If a target API call returns `404` for a resource that has a DB mapping, the mapping is stale (target mutated out-of-band). Bridge must:

1. Delete the `integrations` row from DB
2. Delete `cache:{target}:scim:{type}:{scim_id}` and `cache:{target}:ext:{type}:{external_id}` from Redis
3. Return `404` to caller

## Access Patterns

| Operation | Redis keys touched |
|---|---|
| Get resource by `scim_id` | Read `cache:{target}:scim:{type}:{scim_id}` (miss → query DB, populate cache) |
| Get resource by `external_id` | Read `cache:{target}:ext:{type}:{external_id}` (miss → query DB, populate cache) |
| Create resource | Populate both cache keys on saga completion |
| Delete resource | DEL both cache keys |
| Target API call | INCR + EXPIRE `ratelimit:{target}:window:{ts}` |
