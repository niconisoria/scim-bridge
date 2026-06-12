# Database

PostgreSQL — persistent store for ID mappings and provisioning audit trail.

## Stack

| Layer | Choice |
|---|---|
| Driver | asyncpg |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |

## Schema

### `integrations`

Polymorphic mapping table — one row per provisioned resource per target system.

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

**`operation` values:** `create_user`, `delete_user`, `create_group`, `delete_group`, `add_member`, `remove_member`

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

| Operation | Query |
|---|---|
| Lookup by `scim_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND scim_id=?` |
| Lookup by `external_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND external_id=?` |
| Lookup by `target_id` | `SELECT * FROM integrations WHERE target=? AND resource_type=? AND target_id=?` |
| Create (saga step 0) | `INSERT ... (status='pending')` — UNIQUE blocks duplicate |
| Activate (saga complete) | `UPDATE integrations SET target_id=?, status='active', updated_at=now()` |
| Delete | `DELETE FROM integrations WHERE target=? AND resource_type=? AND scim_id=?` |
| Saga create | `INSERT INTO provisioning_actions ...` |
| Saga step update | `UPDATE provisioning_actions SET status=?, current_step=?, steps=?, updated_at=now()` |
| Saga complete | `UPDATE provisioning_actions SET status='completed', completed_at=now()` |

## Orphaned Sagas on Restart

`provisioning_actions` rows in `running` status with no active process are orphaned. Bridge does not auto-resume — relies on the IdP retrying the operation. Retried create hits step 0, but the `pending` integration row blocks it via UNIQUE constraint.

Cleanup: startup task marks `provisioning_actions WHERE status='running' AND updated_at < now() - interval '5 minutes'` as `failed`. Associated `pending` integration rows are **not deleted** — they prevent duplicate creation on IdP retry (retry hits UNIQUE constraint → `409`). Operator must manually clear stuck `pending` rows.

## Migrations

Alembic manages schema versions. Migration files in `alembic/versions/`. Run on app startup in dev; apply manually before deploying to production.

## Redis Cache Layer

Redis caches hot integration lookups. DB is source of truth. See [redis.md](redis.md).

| Cache Key | Value | TTL |
|---|---|---|
| `cache:{target}:scim:{type}:{scim_id}` | JSON `{target_id, external_id}` | 5 min |
| `cache:{target}:ext:{type}:{external_id}` | JSON `{scim_id, target_id}` | 5 min |
