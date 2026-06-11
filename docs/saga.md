# Saga Orchestrator

All multi-step Brivo provisioning operations use the saga pattern. Each operation defines ordered forward steps and compensating (rollback) steps. State persisted in Redis (→ [redis.md](redis.md)) before execution begins.

## State Machine

**Saga states:** `running` → `completed` | `compensating` → `compensated` | `failed`

**Step states:** `pending` → `running` → `done` | `failed`

On any step failure: transition saga to `compensating`, execute rollbacks in reverse order of completed steps only.

## Retry Policy

Per-step retries via `tenacity`: exponential backoff with jitter, max 3 attempts.
After 3 failures: mark step `failed`, trigger rollback.

## Orphaned Sagas on Restart

If the bridge restarts while a saga is `running`, the saga remains in Redis with status `running` but no process will resume it. On restart, the bridge does **not** auto-resume in-progress sagas — behavior relies on Okta retrying the operation. The retry hits the create pre-check (step 0), which queries Brivo by `externalId` to detect partial state and recover or clean up before proceeding.

## Operations

### Create User

| Step | Forward | Rollback |
|---|---|---|
| 0 | Check `ext:user:{external_id}` in Redis — if found return `409`. If miss: query Brivo `GET /users?externalId={external_id}` — if found rebuild mapping + return `409`. | — |
| 1 | `POST /brivo/users` → save `brivo_id` to saga state | `DELETE /brivo/users/{brivo_id}` |
| 2 | Write `scim:user:{scim_id}` → `{brivo_id, external_id}` and `ext:user:{external_id}` → `scim_id` to Redis | Delete both Redis keys |

### Delete User

| Step | Forward | Rollback |
|---|---|---|
| 1 | Fetch user's Brivo group memberships; save list to saga state | Re-add user to each group |
| 2 | `DELETE` user from each Brivo group | (covered by step 1 rollback) |
| 3 | `DELETE /brivo/users/{brivo_id}` | **Not recoverable** — log structured alert |
| 4 | Read `external_id` from `scim:user:{scim_id}` value; delete `scim:user:{scim_id}` and `ext:user:{external_id}` | Restore both Redis keys |

> Step 3 rollback is unrecoverable. Saga marks `failed`, emits error log with `saga_id`. Okta must retry the full provisioning cycle.

### Delete Group

| Step | Forward | Rollback |
|---|---|---|
| 1 | `DELETE /brivo/groups/{brivo_group_id}` | **Not recoverable** — log structured alert |
| 2 | Read `external_id` from `scim:group:{scim_id}` value; delete `scim:group:{scim_id}` and `ext:group:{external_id}` | Restore both Redis keys |

> Step 1 rollback is unrecoverable (group gone from Brivo). Saga marks `failed`, emits error log with `saga_id`. Okta must retry the full provisioning cycle.

> Unlike Delete User, group membership cleanup is not needed — Brivo removes all member associations when a group is deleted.

### Create Group (with members)

| Step | Forward | Rollback |
|---|---|---|
| 0 | Check `ext:group:{external_id}` in Redis — if found return `409`. If miss: query Brivo `GET /groups?externalId={external_id}` — if found rebuild mapping + return `409`. | — |
| 1 | `POST /brivo/groups` → save `brivo_group_id` to saga state | `DELETE /brivo/groups/{brivo_group_id}` |
| 2 | Write `scim:group:{scim_id}` → `{brivo_group_id, external_id}` and `ext:group:{external_id}` → `scim_id` to Redis | Delete both Redis keys |
| 3 | For each member: resolve `scim_user_id` → `brivo_user_id` from Redis (if missing → `400`, abort before step 3 starts); `PUT /v1/api/groups/{groupId}/users/{userId}`; append `userId` to `saga.steps[3].added_members` in Redis after each success | `DELETE /v1/api/groups/{groupId}/users/{userId}` for each ID in `added_members` in reverse |

> Step 3 member resolution: if any `scim_user_id` has no Redis mapping, the entire saga aborts before executing any Brivo member calls — return `400` to caller.

> Step 3 rollback uses `added_members` accumulated in saga state to know exactly which members were successfully added before the failure.

### Add Member to Group (PATCH `add`)

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id` → `brivo_user_id` from Redis; if missing → `400` | — |
| 2 | `PUT /v1/api/groups/{brivo_group_id}/users/{brivo_user_id}` | `DELETE /v1/api/groups/{brivo_group_id}/users/{brivo_user_id}` |

### Remove Member from Group (PATCH `remove`)

| Step | Forward | Rollback |
|---|---|---|
| 1 | Resolve `scim_user_id` → `brivo_user_id` from Redis; if missing → `400` | — |
| 2 | `DELETE /v1/api/groups/{brivo_group_id}/users/{brivo_user_id}` | `PUT /v1/api/groups/{brivo_group_id}/users/{brivo_user_id}` |

### Update User / Group (PUT or PATCH `replace`)

Single Brivo call — no saga needed. `tenacity` retries directly. Idempotent by design.
