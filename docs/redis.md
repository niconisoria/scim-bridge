# Redis Integration

Redis serves two purposes:

1. **ID mapping store** — permanent store for `scim_id ↔ target_id ↔ external_id`. No TTL. No database needed.
2. **Brivo response cache** — TTL-based cache absorbing Brivo read traffic to stay within rate limit budget.

## Key Inventory

### ID Mappings (permanent — no TTL)

| Key | Type | Value |
|---|---|---|
| `idmap:{target}:scim:{type}:{scim_id}` | string | JSON `{ target_id, external_id, created_at }` |
| `idmap:{target}:ext:{type}:{external_id}` | string | JSON `{ scim_id, target_id }` |
| `idmap:{target}:tid:{type}:{target_id}` | string | JSON `{ scim_id, external_id }` |

`type` is `user` or `group`. `target` is the downstream system identifier (e.g. `brivo`).

All three written atomically on saga completion. No TTL — deleted only when the resource is deleted. `tid` key enables O(1) `target_id → scim_id` lookup required for member hydration.

`created_at` stored in the `scim` key is used to populate `meta.created` in SCIM responses (Brivo does not expose creation timestamps).

### Idempotency Locks (short TTL)

| Key | Type | Value | TTL |
|---|---|---|---|
| `lock:{target}:create:{type}:{external_id}` | string | `saga_id` | 300 s |

Set with `SET NX EX 300` at saga step 0. Atomic duplicate-create guard — replaces the DB UNIQUE constraint. Deleted on saga completion or rollback. Expires automatically on bridge crash; IdP retry succeeds after the 5-minute window.

### Brivo Response Cache (TTL)

| Key | Type | Value | TTL |
|---|---|---|---|
| `cache:{target}:user:{target_id}` | string | JSON Brivo user object | 5 min |
| `cache:{target}:group:{target_id}` | string | JSON Brivo group object | 5 min |
| `cache:{target}:group:{target_id}:members` | string | JSON array of Brivo user IDs | 5 min |

Cache-aside: read cache first, on miss call Brivo and populate. Explicitly invalidated on write; TTL is a safety net.

## Access Patterns

### Read path

| Operation | Keys touched |
|---|---|
| Resolve `scim_id → target_id` | Read `idmap:{target}:scim:{type}:{scim_id}` |
| Resolve `external_id → scim_id` | Read `idmap:{target}:ext:{type}:{external_id}` |
| GET user/group | Read `cache:{target}:user/group:{target_id}` → miss: Brivo GET, populate cache |
| GET group members | Read `cache:{target}:group:{target_id}:members` → miss: Brivo GET, populate cache |
| List / filter | Read `cache:{target}:user/group:{target_id}` per resource; on miss: Brivo GET per resource |

### Write path (saga)

| Operation | Keys touched |
|---|---|
| Create resource (step 0) | `SET NX EX 300 lock:{target}:create:{type}:{external_id}` |
| Create resource (complete) | DEL lock key; SET `idmap:scim`, `idmap:ext`, and `idmap:tid` keys (no TTL) |
| Update resource | DEL `cache:{target}:user/group:{target_id}` |
| Add/remove group member | DEL `cache:{target}:group:{target_id}:members` |
| Delete resource | DEL all three idmap keys + all cache keys for the resource |

## Invalidation Rules

| Key pattern | Invalidated by |
|---|---|
| `idmap:{target}:scim:{type}:{scim_id}` | Delete User saga; Delete Group saga |
| `idmap:{target}:ext:{type}:{external_id}` | Delete User saga; Delete Group saga |
| `idmap:{target}:tid:{type}:{target_id}` | Delete User saga; Delete Group saga |
| `cache:{target}:user:{target_id}` | Update User (write-modify-write); Delete User saga |
| `cache:{target}:group:{target_id}` | PATCH/PUT group attrs; Delete Group saga |
| `cache:{target}:group:{target_id}:members` | Add Member saga; Remove Member saga; Update Group saga; Delete Group saga |
