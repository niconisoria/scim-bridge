# Saga Orchestrator

All multi-step target provisioning operations use the saga pattern. Each operation defines ordered forward steps and compensating (rollback) steps. State persisted in PostgreSQL `provisioning_actions` table (→ [database.md](database.md)) before execution begins.

## State Machine

**Saga states:** `running` → `completed` | `compensating` → `compensated` | `failed`

**Step states:** `pending` → `running` → `done` | `failed`

On any step failure: transition saga to `compensating`, execute rollbacks in reverse order of completed steps only.

## Retry Policy

Per-step retries via `tenacity`: exponential backoff with jitter, max 3 attempts.
After 3 failures: mark step `failed`, trigger rollback.

## Orphaned Sagas on Restart

If the bridge restarts while a saga is `running`, the row remains in `provisioning_actions` with status `running` but no process will resume it. On restart, the bridge does **not** auto-resume in-progress sagas — behavior relies on the IdP retrying the operation.

Cleanup: startup task marks stale `running` sagas as `failed` and deletes associated `pending` integration rows. The Brivo fallback check in step 0 (see below) then catches any resources that were partially created in the target before the crash.

## Operations

### Create User

| Step | Forward | Rollback |
|---|---|---|
| 0 | **Lock + idempotency check:** `INSERT INTO integrations (..., status='pending')`. On `UniqueViolationError` → return `409`. On success: query target `GET /users?externalId={external_id}` as crash-recovery check — if found, `UPDATE` pending row to `status='active'` with `target_id`, return `409`. Record saga in `provisioning_actions`. | — |
| 1 | `POST /target/users` → save `target_id` to saga steps JSONB | `DELETE /target/users/{target_id}` |
| 2 | `UPDATE integrations SET target_id=?, status='active'`. Populate Redis cache. | DELETE integration row; invalidate Redis cache |

> Step 0 Brivo fallback guards against crash-recovery: if the bridge crashed after step 1 but before step 2, startup cleanup deletes the orphaned `pending` row. The IdP retry would succeed at INSERT, then the Brivo fallback query detects the existing resource and returns `409` without creating a duplicate.

### Delete User

| Step | Forward | Rollback |
|---|---|---|
| 1 | Fetch user's target group memberships; save list to saga steps JSONB | Re-add user to each group |
| 2 | `DELETE` user from each target group | (covered by step 1 rollback) |
| 3 | `DELETE /target/users/{target_id}` | **Not recoverable** — log structured alert |
| 4 | `DELETE FROM integrations WHERE ...`. Invalidate Redis cache. | Restore integration row; repopulate cache |

> Step 3 rollback is unrecoverable. Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

### Delete Group

| Step | Forward | Rollback |
|---|---|---|
| 1 | `DELETE /target/groups/{target_group_id}` | **Not recoverable** — log structured alert |
| 2 | `DELETE FROM integrations WHERE ...`. Invalidate Redis cache. | Restore integration row; repopulate cache |

> Step 1 rollback is unrecoverable (group gone from target). Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

> Unlike Delete User, group membership cleanup is not needed — target removes all member associations when a group is deleted.

### Create Group (with members)

| Step | Forward | Rollback |
|---|---|---|
| 0 | **Lock + idempotency check:** `INSERT INTO integrations (..., resource_type='group', status='pending')`. On `UniqueViolationError` → return `409`. On success: query target `GET /groups?externalId={external_id}` as crash-recovery check — if found, `UPDATE` pending row to `status='active'` with `target_id`, return `409`. Record saga in `provisioning_actions`. | — |
| 1 | `POST /target/groups` → save `target_group_id` to saga steps JSONB | `DELETE /target/groups/{target_group_id}` |
| 2 | `UPDATE integrations SET target_id=?, status='active'`. Populate Redis cache. | DELETE integration row; invalidate Redis cache |
| 3 | For each member: resolve `scim_user_id` → `target_user_id` from DB/cache (if missing → `400`, abort before step 3 starts); `PUT /target/groups/{groupId}/users/{userId}`; append `userId` to `saga.steps[3].added_members` in JSONB after each success | `DELETE /target/groups/{groupId}/users/{userId}` for each ID in `added_members` in reverse |

> Step 3 member resolution: if any `scim_user_id` has no integration mapping, the entire saga aborts before executing any target member calls — return `400` to caller.

> Step 3 rollback uses `added_members` accumulated in saga steps JSONB to know exactly which members were successfully added before the failure.

### Add Member to Group (PATCH `add`)

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id` → `target_user_id` from DB/cache; if missing → `400` | — |
| 2 | `PUT /target/groups/{target_group_id}/users/{target_user_id}` | `DELETE /target/groups/{target_group_id}/users/{target_user_id}` |

### Remove Member from Group (PATCH `remove`)

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id` → `target_user_id` from DB/cache; if missing → `400` | — |
| 2 | `DELETE /target/groups/{target_group_id}/users/{target_user_id}` | `PUT /target/groups/{target_group_id}/users/{target_user_id}` |

### Update User / Group (PUT or PATCH `replace`)

Single target call — no saga needed. `tenacity` retries directly. Idempotent by design.
