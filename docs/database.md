# Database

PostgreSQL — persistent store for resource state (users, groups, members), ID mappings, and provisioning audit trail.

## Stack

| Layer | Choice |
|---|---|
| Driver | asyncpg |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |

## Schema

Bridge DB is source of truth for all reads. Resource state (user attributes, group attributes, memberships) lives here. Brivo receives every write but is never queried on the read path.

### `integrations`

ID mapping table — one row per provisioned resource per target system. Lifecycle gatekeeper for saga idempotency.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, default `gen_random_uuid()` |
| `target` | VARCHAR | NOT NULL — e.g. `'brivo'` |
| `resource_type` | ENUM('user','group') | NOT NULL |
| `scim_id` | UUID | NOT NULL |
| `external_id` | VARCHAR | NOT NULL |
| `target_id` | VARCHAR | nullable — null until saga completes |
| `status` | ENUM('pending','active') | NOT NULL, default `'pending'` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**Role of each ID:**

| Column | Owner | Meaning |
|---|---|---|
| `scim_id` | Bridge | Bridge-generated UUID, stable resource identity |
| `external_id` | IdP (Okta) | Okta's `externalId` — used for idempotency checks |
| `target_id` | Target (Brivo) | Target system's internal ID — null until provisioning completes |

**Indexes / Constraints:**
- UNIQUE `(target, resource_type, scim_id)`
- UNIQUE `(target, resource_type, external_id)`
- UNIQUE `(target, resource_type, target_id)` WHERE `status = 'active'`

**`status` lifecycle:**
- `pending` — row inserted at saga step 0 (before target call); UNIQUE constraint acts as distributed lock
- `active` — set when saga completes (`target_id` written)
- On saga rollback/failure: DELETE the row

---

### `users`

SCIM attribute store for user resources. Written at saga step 0 alongside the `integrations` row; only visible to reads when the paired `integrations` row has `status='active'`.

| Column | Type | Constraints |
|---|---|---|
| `scim_id` | UUID | PK, FK → `integrations.scim_id` |
| `username` | VARCHAR | NOT NULL — email address used as canonical identity; stored lowercase-normalized |
| `given_name` | VARCHAR | NOT NULL |
| `family_name` | VARCHAR | NOT NULL |
| `email` | VARCHAR | NOT NULL |
| `phone` | VARCHAR | nullable |
| `active` | BOOLEAN | NOT NULL, default `true` |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**Indexes:**
- UNIQUE `username` — stored lowercase; supports case-insensitive `userName eq` filter via O(1) index scan
- INDEX `email`

---

### `groups`

SCIM attribute store for group resources. Same lifecycle as `users` — written at saga step 0.

| Column | Type | Constraints |
|---|---|---|
| `scim_id` | UUID | PK, FK → `integrations.scim_id` |
| `display_name` | VARCHAR(35) | NOT NULL — Brivo's 35-char limit enforced at DB level |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**Indexes:**
- INDEX `display_name` — supports `displayName eq` filter

---

### `group_members`

Group membership join table. Written by Add Member saga; deleted by Remove Member saga.

| Column | Type | Constraints |
|---|---|---|
| `group_scim_id` | UUID | FK → `integrations.scim_id` (resource_type='group') |
| `user_scim_id` | UUID | FK → `integrations.scim_id` (resource_type='user') |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |

**PK:** `(group_scim_id, user_scim_id)`

### `provisioning_actions`

Audit log of all saga executions.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK (= saga_id) |
| `target` | VARCHAR | NOT NULL |
| `operation` | ENUM | NOT NULL — see values below |
| `status` | ENUM | NOT NULL — see values below |
| `current_step` | SMALLINT | NOT NULL, default `0` |
| `steps` | JSONB | NOT NULL, default `'[]'` |
| `resource_type` | ENUM('user','group') | NOT NULL |
| `external_id` | VARCHAR | NOT NULL |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default `now()` |
| `completed_at` | TIMESTAMPTZ | nullable |

**`operation` values:** `create_user`, `delete_user`, `create_group`, `update_group`, `delete_group`, `add_member`, `remove_member`

Non-saga operations (Update User, PATCH replace group attrs, PATCH replace members) are not recorded here — they are single read-modify-write calls with `tenacity` retries, not sagas. `update_group` covers PATCH replace members when it runs as a full diff saga.

**`status` values:** `running`, `completed`, `compensating`, `compensated`, `failed`

**Indexes:**
- `(target, resource_type, external_id)` — look up history by resource
- `status` — find running/failed sagas

**`steps` JSONB structure:**
```json
[
  { "step": 0, "status": "done", "data": {} },
  { "step": 1, "status": "done", "data": { "target_id": "abc123" } },
  { "step": 2, "status": "running", "data": {} }
]
```

## Concurrent Create Race Condition

```sql
INSERT INTO integrations (target, resource_type, external_id, scim_id, status)
VALUES ('brivo', 'user', '{external_id}', '{scim_id}', 'pending')
```

Concurrent request with same `(target, resource_type, external_id)` → UNIQUE constraint raises `UniqueViolationError` → return `409`. No Redis NX lock needed.

## Access Patterns

### ID Resolution

| Operation | Query |
|---|---|
| Lookup by `scim_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND scim_id=?` |
| Lookup by `external_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND external_id=?` |
| Lookup by `target_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND target_id=?` |
| Create (saga step 0) | `INSERT INTO integrations ... (status='pending')` — UNIQUE blocks duplicate |
| Activate (saga complete) | `UPDATE integrations SET target_id=?, status='active', updated_at=now()` |
| Delete | `DELETE FROM integrations WHERE target=? AND resource_type=? AND scim_id=?` |

### Resource Reads (SCIM read path)

All read queries join `integrations` on `status='active'` — pending resources are invisible to callers.

| Operation | Query |
|---|---|
| Get user by `scim_id` | `SELECT u.*, i.external_id, i.target_id FROM users u JOIN integrations i ON u.scim_id=i.scim_id WHERE i.scim_id=? AND i.status='active'` |
| Get group by `scim_id` | `SELECT g.*, i.external_id FROM groups g JOIN integrations i ON g.scim_id=i.scim_id WHERE i.scim_id=? AND i.status='active'` |
| List users (paginated) | `SELECT ... FROM users u JOIN integrations i ... WHERE i.target=? AND i.status='active' ORDER BY u.created_at ASC LIMIT ? OFFSET ?` |
| List groups (paginated) | Same pattern on `groups` |
| Filter `userName eq` | `SELECT ... WHERE u.username=? AND i.status='active'` — index scan |
| Filter `displayName eq` | `SELECT ... WHERE g.display_name=? AND i.status='active'` — index scan |
| Filter `externalId eq` | `SELECT ... WHERE i.external_id=? AND i.status='active'` |
| Get group members | `SELECT gm.user_scim_id FROM group_members gm WHERE gm.group_scim_id=?` |

### Resource Writes (saga write path)

| Operation | Query |
|---|---|
| Create user (step 0) | `INSERT INTO users (scim_id, username, given_name, ...) ...` |
| Update user attributes | `UPDATE users SET given_name=?, ..., updated_at=now() WHERE scim_id=?` |
| Delete user | `DELETE FROM users WHERE scim_id=?` |
| Create group (step 0) | `INSERT INTO groups (scim_id, display_name) ...` |
| Update group attributes | `UPDATE groups SET display_name=?, updated_at=now() WHERE scim_id=?` |
| Delete group | `DELETE FROM group_members WHERE group_scim_id=?; DELETE FROM groups WHERE scim_id=?` |
| Add member | `INSERT INTO group_members (group_scim_id, user_scim_id) VALUES (?, ?) ON CONFLICT DO NOTHING` |
| Remove member | `DELETE FROM group_members WHERE group_scim_id=? AND user_scim_id=?` |

### Saga

| Operation | Query |
|---|---|
| Saga create | `INSERT INTO provisioning_actions ...` |
| Saga step update | `UPDATE provisioning_actions SET status=?, current_step=?, steps=?, updated_at=now()` |
| Saga complete | `UPDATE provisioning_actions SET status='completed', completed_at=now()` |

## Orphaned Sagas on Restart

`provisioning_actions` rows in `running` status with no active process are orphaned. Bridge does not auto-resume — relies on the IdP retrying the operation. Retried create hits step 0, but the `pending` integration row blocks it via UNIQUE constraint.

Cleanup: startup task marks `provisioning_actions WHERE status='running' AND updated_at < now() - interval '5 minutes'` as `failed`. Associated `pending` integration rows are **not deleted** — they prevent duplicate creation on IdP retry (retry hits UNIQUE constraint → `409`). Associated `users`/`groups` rows written at step 0 are also **not deleted** — operator must manually clear both when clearing stuck `pending` rows.

## Reconciliation

Out-of-band Brivo mutations (direct API or UI edits outside the bridge) are not visible to the bridge until the reconcile job runs. The bridge DB may be briefly stale between cycles — this is acceptable per the architecture constraint.

**Reconcile job behavior:**

1. Paginate all `active` resources from bridge DB
2. For each resource, `GET /target/{resource}/{target_id}` from Brivo
3. If Brivo returns `404`: resource deleted out-of-band → `DELETE FROM users/groups/group_members WHERE scim_id=?`; `DELETE FROM integrations WHERE scim_id=?`; invalidate Redis cache
4. If Brivo returns different attributes: `UPDATE users/groups SET ...` with Brivo values
5. Members: compare `group_members` table against Brivo group member list; insert/delete rows to reconcile

Reconcile job runs on a configurable schedule (e.g., every 15 minutes). Uses the same rate limiter as the write path.

## Migrations

Alembic manages schema versions. Migration files in `alembic/versions/`. Run on app startup in dev; apply manually before deploying to production.

## Redis Cache Layer

Redis caches hot DB lookups. Bridge DB is source of truth — Redis is a read-through cache only. See [redis.md](redis.md).

| Cache Key | Value | TTL |
|---|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | JSON `{target_id, external_id}` | 5 min |
| `cache:{target}:ext:{type}:{external_id}` | JSON `{scim_id, target_id}` | 5 min |
