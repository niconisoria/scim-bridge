# Architecture

Automated identity lifecycle management from Okta into Brivo via SCIM 2.0.
Ensures reliability under rate limits, incomplete downstream data, and multi-step provisioning workflows.

## Flow

```mermaid
flowchart LR
    Okta -->|SCIM 2.0| Bridge["SCIM Bridge\n(FastAPI)"]
    Bridge <-->|reads + writes| DB[(PostgreSQL)]
    Bridge --> Saga["Saga Orchestrator"]
    Saga -->|HTTP| Brivo["Mock Brivo Client"]
    Saga -->|resource writes + saga state| DB
    Bridge <-->|cache| Redis
    Recon["Reconcile Job"] -->|poll| Brivo
    Recon -->|sync out-of-band changes| DB
```

**Bridge DB is the source of truth for all reads.** Brivo is the authoritative downstream target — it receives every write, but is never queried on the read path. The reconcile job catches out-of-band Brivo mutations and syncs them back to the bridge DB.

## Roles

| Actor | Role |
|---|---|
| Okta | Identity Provider (IdP) — initiates provisioning, owns `external_id` |
| SCIM Bridge | Intermediary SCIM server — owns `scim_id`, translates to target API |
| Brivo | Target system — receives provisioning actions, owns `target_id` |

## Components

| Component | Responsibility | Detail |
|---|---|---|
| SCIM Bridge | Translate SCIM 2.0 operations to target API calls; serves all reads from DB | [scim-server.md](scim-server.md) |
| Mock Brivo Client | Simulate Brivo API with configurable failure modes | [brivo-mock.md](brivo-mock.md) |
| Rate Limiter | Enforce target request rate limit | [rate-limiter.md](rate-limiter.md) |
| Saga Orchestrator | Coordinate multi-step operations with rollback; writes resource state to DB | [saga.md](saga.md) |
| PostgreSQL | Source of truth: resource state (users, groups, members) + ID mappings + audit trail | [database.md](database.md) |
| Redis | Cache layer for hot resource and ID lookups | [redis.md](redis.md) |
| Reconcile Job | Polls Brivo periodically; syncs out-of-band mutations back to bridge DB | [database.md § Reconciliation](database.md) |

## Constraints

- Bridge DB is source of truth for reads — never query Brivo on the read path
- Target system enforces a rate limit — enforce at client layer, never drop under normal load
- Target responses may be partial/incomplete — handle gracefully on write path only
- All operations must be **idempotent** and retry-safe
- Multi-step operations must define forward + compensating (rollback) actions
- Out-of-band Brivo mutations are tolerated until the next reconcile cycle — bridge DB may be briefly stale

## Deliverables

| Deliverable | Doc |
|---|---|
| FastAPI SCIM server | [scim-server.md](scim-server.md) |
| Mock Brivo client | [brivo-mock.md](brivo-mock.md) |
| Rate limiter module | [rate-limiter.md](rate-limiter.md) |
| Saga orchestrator | [saga.md](saga.md) |
| Database integration | [database.md](database.md) |
| Redis integration | [redis.md](redis.md) |
| Infra (Docker + Compose) | [infra.md](infra.md) |
| Testing strategy | [testing.md](testing.md) |
| Structured logging | [logging.md](logging.md) |
