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

Cleanup: startup task marks stale `running` sagas as `failed`. Associated `pending` integration rows are **not deleted** — they act as tombstones preventing duplicate creation on IdP retry (retry hits UNIQUE constraint on `external_id` → `409`). Operator must manually clear stuck `pending` rows after investigating.

## Operations

### Create User

| Step | Forward | Rollback |
|---|---|---|
| 0 | **Lock + idempotency check:** `INSERT INTO integrations (..., status='pending')`. `INSERT INTO users (scim_id, username, given_name, ...)`. On `UniqueViolationError` on integrations → return `409`. Record saga in `provisioning_actions`. | DELETE users row; DELETE integrations row |
| 1 | `POST /target/users` → save `target_id` to saga steps JSONB | `DELETE /target/users/{target_id}` |
| 2 | `UPDATE integrations SET target_id=?, status='active'`. Populate Redis cache. | DELETE users row; DELETE integrations row; invalidate Redis cache |

### Delete User

Router resolves `scim_id` (URL param) → `target_id` via DB/cache before invoking saga; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Fetch user's group memberships from `group_members` table; save list to saga steps JSONB | Re-insert rows into `group_members`; re-add user to each target group |
| 2 | `DELETE FROM group_members WHERE user_scim_id=?`; `DELETE` user from each target group | (covered by step 1 rollback) |
| 3 | `DELETE /target/users/{target_id}` | **Not recoverable** — log structured alert |
| 4 | `DELETE FROM users WHERE scim_id=?`; `DELETE FROM integrations WHERE ...`. Invalidate Redis cache. | Restore users row; restore integration row; repopulate cache |

> Step 3 rollback is unrecoverable. Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

### Delete Group

Router resolves `scim_id` (URL param) → `target_group_id` via DB/cache before invoking saga; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | `DELETE /target/groups/{target_group_id}` | **Not recoverable** — log structured alert |
| 2 | `DELETE FROM group_members WHERE group_scim_id=?`; `DELETE FROM groups WHERE scim_id=?`; `DELETE FROM integrations WHERE ...`. Invalidate Redis cache. | Restore groups row; restore integrations row; repopulate cache |

> Step 1 rollback is unrecoverable (group gone from target). Saga marks `failed`, emits error log with `saga_id`. IdP must retry the full provisioning cycle.

> `group_members` rows are deleted in step 2 alongside the group — target removes its own member associations when the group is deleted, so bridge DB must mirror that.

### Create Group (with members)

| Step | Forward | Rollback |
|---|---|---|
| 0 | **Lock + idempotency check:** `INSERT INTO integrations (..., resource_type='group', status='pending')`. `INSERT INTO groups (scim_id, display_name)`. On `UniqueViolationError` on integrations → return `409`. Record saga in `provisioning_actions`. | DELETE groups row; DELETE integrations row |
| 1 | `POST /target/groups` → save `target_group_id` to saga steps JSONB | `DELETE /target/groups/{target_group_id}` |
| 2 | `UPDATE integrations SET target_id=?, status='active'`. Populate Redis cache. | DELETE groups row; DELETE integrations row; invalidate Redis cache |
| 3 | For each member: resolve `scim_user_id` → `target_user_id` from DB/cache (if missing → `400`, abort before step 3 starts); `PUT /target/groups/{target_group_id}/users/{target_user_id}`; `INSERT INTO group_members (group_scim_id, user_scim_id)`; append `target_user_id` to `saga.steps[3].added_members` in JSONB after each success | `DELETE FROM group_members WHERE group_scim_id=? AND user_scim_id=?`; `DELETE /target/groups/{target_group_id}/users/{target_user_id}` for each in `added_members` in reverse |

> Step 3 member resolution: if any `scim_user_id` has no integration mapping, the entire saga aborts before executing any target member calls — return `400` to caller.

> Step 3 rollback uses `added_members` accumulated in saga steps JSONB to know exactly which members were successfully added before the failure.

### Add Member(s) to Group (PATCH `add`)

Router resolves `scim_group_id` (URL param) → `target_group_id` via DB/cache before invoking saga; if missing → `404`.

One `add` op may include N members in `value[]`. Resolve all `scim_user_id → target_user_id` upfront (return `400` if any missing), then execute each as a separate step — same pattern as Create Group step 3.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve all `scim_user_id → target_user_id` from DB/cache; if any missing → `400` | — |
| 2 | For each member: `PUT /target/groups/{target_group_id}/users/{target_user_id}`; `INSERT INTO group_members (group_scim_id, user_scim_id) ON CONFLICT DO NOTHING`; append `target_user_id` to `added_members` in saga JSONB | `DELETE FROM group_members WHERE ...`; `DELETE /target/.../users/{target_user_id}` for each in `added_members` in reverse |

### Remove Member from Group (PATCH `remove`)

Router resolves `scim_group_id` (URL param) → `target_group_id` via DB/cache before invoking saga; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id` → `target_user_id` from DB/cache; if missing → `400` | — |
| 2 | `DELETE /target/groups/{target_group_id}/users/{target_user_id}`; `DELETE FROM group_members WHERE group_scim_id=? AND user_scim_id=?` | `INSERT INTO group_members ...`; `PUT /target/groups/{target_group_id}/users/{target_user_id}` |

### Update User (PUT or PATCH `replace`)

Router resolves `scim_id` → `target_id` via DB/cache before calling Brivo; if missing → `404`.

Read-modify-write — no saga:
1. `SELECT * FROM users WHERE scim_id=?` → current SCIM state (no Brivo call)
2. Merge PUT fields or PATCH replace ops into full user object
3. `PUT /target/users/{target_id}` with mapped Brivo payload — `tenacity` retries on failure
4. `UPDATE users SET ..., updated_at=now() WHERE scim_id=?`
5. Return updated SCIM resource from bridge DB

### Update Group (PUT)

Router resolves `scim_id` → `target_group_id` via DB/cache before invoking saga; if missing → `404`.

| Step | Forward | Rollback |
|---|---|---|
| 1 | Save current `display_name` from `groups` table to saga JSONB; `PUT /target/groups/{target_group_id}` with new `name`; `UPDATE groups SET display_name=? WHERE scim_id=?` | `PUT /target/groups/{target_group_id}` with original name; `UPDATE groups SET display_name=original WHERE scim_id=?` |
| 2 | `SELECT user_scim_id FROM group_members WHERE group_scim_id=?` → save current member list to saga JSONB (no Brivo call) | — |
| 3 | Resolve all new `members[]` `scim_id → target_user_id` (if any missing → `400`, abort) | — |
| 4 | Add new members: `PUT /target/groups/{target_group_id}/users/{target_user_id}` for each; `INSERT INTO group_members ...`; track in `added_members` | `DELETE FROM group_members ...`; `DELETE /target/.../users/{target_user_id}` for each in `added_members` |
| 5 | Remove old members: `DELETE /target/groups/{target_group_id}/users/{target_user_id}` for each; `DELETE FROM group_members ...`; track in `removed_members` | `INSERT INTO group_members ...`; `PUT /target/.../users/{target_user_id}` for each in `removed_members` |

### PATCH `replace` Group Attributes

Router resolves `scim_id` → `target_group_id` via DB/cache before calling Brivo; if missing → `404`.

No saga: `PUT /target/groups/{target_group_id}` with updated `name`; `UPDATE groups SET display_name=? WHERE scim_id=?`. `tenacity` retries on Brivo call.
