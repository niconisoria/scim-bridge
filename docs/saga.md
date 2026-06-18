# Saga Orchestrator

All multi-step target provisioning operations use the saga pattern. Each operation defines ordered forward steps and compensating (rollback) steps. Saga state is in-memory — on crash, IdP retries and the idempotency lock (Redis) gates re-entry.

## State Machine

**Saga states:** `running` → `completed` | `compensating` → `compensated` | `failed`

**Step states:** `pending` → `running` → `done` | `failed`

On any step failure: transition saga to `compensating`, execute rollbacks in reverse order of completed steps only.

## Retry Policy

Per-step retries via `tenacity`: exponential backoff with jitter, max 3 attempts.
After 3 failures: mark step `failed`, trigger rollback.

## Crash Recovery

Saga state is in-memory. Bridge crash = in-progress saga is lost. The idempotency lock (`lock:{target}:create:{type}:{external_id}`, TTL 300 s) expires automatically. IdP retries → `SET NX` succeeds → new saga proceeds cleanly.

## Operations

### Create User

| Step | Forward | Rollback |
|---|---|---|
| 0 | Generate `scim_id` (UUID v4). `SET NX EX 300 lock:brivo:create:user:{external_id}` — if key exists → `409`. | DEL lock key |
| 1 | `POST /target/users` → save `target_id` to saga state | `DELETE /target/users/{target_id}` |
| 2 | Write `idmap:brivo:scim:user:{scim_id}` and `idmap:brivo:ext:user:{external_id}` (permanent, no TTL). DEL lock key. | DEL both idmap keys |

### Delete User

Router resolves `scim_id` → `target_id` via Redis idmap; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | `GET /target/groups` filtered by user membership (or Brivo member list endpoint); save group `target_id` list to saga state | — |
| 2 | For each group: `DELETE /target/groups/{target_group_id}/users/{target_id}`; DEL `cache:brivo:group:{target_group_id}:members` | Re-add user to each group; repopulate member cache |
| 3 | `DELETE /target/users/{target_id}` | **Not recoverable** — log structured alert |
| 4 | DEL `idmap:brivo:scim:user:{scim_id}`; DEL `idmap:brivo:ext:user:{external_id}`; DEL `cache:brivo:user:{target_id}` | Restore idmap keys |

> Step 3 rollback is unrecoverable. Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

### Delete Group

Router resolves `scim_id` → `target_group_id` via Redis idmap; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | `DELETE /target/groups/{target_group_id}` | **Not recoverable** — log structured alert |
| 2 | DEL `idmap:brivo:scim:group:{scim_id}`; DEL `idmap:brivo:ext:group:{external_id}`; DEL `cache:brivo:group:{target_group_id}`; DEL `cache:brivo:group:{target_group_id}:members` | Restore idmap keys |

> Step 1 rollback is unrecoverable (group gone from Brivo). Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

### Create Group (with members)

| Step | Forward | Rollback |
|---|---|---|
| 0 | Generate `scim_id` (UUID v4). `SET NX EX 300 lock:brivo:create:group:{external_id}` — if key exists → `409`. | DEL lock key |
| 1 | `POST /target/groups` → save `target_group_id` to saga state | `DELETE /target/groups/{target_group_id}` |
| 2 | Write `idmap:brivo:scim:group:{scim_id}` and `idmap:brivo:ext:group:{external_id}` (permanent). DEL lock key. | DEL both idmap keys |
| 3 | For each member: resolve `scim_user_id → target_user_id` from Redis idmap (if any missing → `400`, abort before step 3 starts); `PUT /target/groups/{target_group_id}/users/{target_user_id}`; append `target_user_id` to `added_members` in saga state after each success. DEL `cache:brivo:group:{target_group_id}:members`. | `DELETE /target/groups/{target_group_id}/users/{target_user_id}` for each in `added_members` in reverse; DEL cache key |

> Step 3 member resolution: if any `scim_user_id` has no idmap entry, the entire saga aborts before executing any Brivo member calls — return `400` to caller.

### Add Member(s) to Group (PATCH `add`)

Router resolves `scim_group_id` → `target_group_id` via Redis idmap; if missing → `404`.

One `add` op may include N members in `value[]`. Resolve all upfront (return `400` if any missing), then execute each.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve all `scim_user_id → target_user_id` from Redis idmap; if any missing → `400` | — |
| 2 | For each member: `PUT /target/groups/{target_group_id}/users/{target_user_id}`; append to `added_members` in saga state. DEL `cache:brivo:group:{target_group_id}:members`. | `DELETE /target/.../users/{target_user_id}` for each in `added_members` in reverse; DEL cache key |

### Remove Member from Group (PATCH `remove`)

Router resolves `scim_group_id` → `target_group_id` via Redis idmap; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id → target_user_id` from Redis idmap; if missing → `400` | — |
| 2 | `DELETE /target/groups/{target_group_id}/users/{target_user_id}`. DEL `cache:brivo:group:{target_group_id}:members`. | `PUT /target/groups/{target_group_id}/users/{target_user_id}`; repopulate cache |

### Update User (PUT or PATCH `replace`)

Router resolves `scim_id → target_id` via Redis idmap; if missing → `404`.

Read-modify-write — no saga:
1. Read `cache:brivo:user:{target_id}` → on miss: `GET /target/users/{target_id}`, populate cache
2. Merge PUT fields or PATCH replace ops into full Brivo user object
3. `PUT /target/users/{target_id}` — `tenacity` retries on failure
4. DEL `cache:brivo:user:{target_id}`
5. Return updated resource (map Brivo response → SCIM)

### Update Group (PUT)

Router resolves `scim_id → target_group_id` via Redis idmap; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Read current group from `cache:brivo:group:{target_group_id}` (miss → Brivo GET); save `name` to saga state; `PUT /target/groups/{target_group_id}` with new `name`; DEL group cache key | `PUT /target/groups/{target_group_id}` with original name; DEL cache key |
| 2 | Fetch current member list from `cache:brivo:group:{target_group_id}:members` (miss → Brivo GET); save to saga state | — |
| 3 | Resolve all new `members[]` `scim_id → target_user_id` from Redis idmap (if any missing → `400`, abort) | — |
| 4 | Add new members: `PUT /target/groups/{target_group_id}/users/{target_user_id}` for each; track in `added_members` | `DELETE /target/.../users/{target_user_id}` for each in `added_members` |
| 5 | Remove old members: `DELETE /target/groups/{target_group_id}/users/{target_user_id}` for each; track in `removed_members`. DEL `cache:brivo:group:{target_group_id}:members`. | `PUT /target/.../users/{target_user_id}` for each in `removed_members`; DEL cache key |

### PATCH `replace` Group Attributes

Router resolves `scim_id → target_group_id` via Redis idmap; if missing → `404`.

No saga: `PUT /target/groups/{target_group_id}` with updated `name`; DEL `cache:brivo:group:{target_group_id}`. `tenacity` retries on Brivo call.
