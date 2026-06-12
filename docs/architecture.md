# Architecture

Automated identity lifecycle management from Okta into Brivo via SCIM 2.0.
Ensures reliability under rate limits, incomplete downstream data, and multi-step provisioning workflows.

## Flow

```mermaid
flowchart LR
    Okta -->|SCIM 2.0| Bridge["SCIM Bridge\n(FastAPI)"]
    Bridge --> Saga["Saga Orchestrator"]
    Saga -->|HTTP| Brivo["Mock Brivo Client"]
    Saga <-->|saga state + ID mappings| DB[(PostgreSQL)]
    Bridge <-->|cache| Redis
```

## Roles

| Actor | Role |
|---|---|
| Okta | Identity Provider (IdP) — initiates provisioning, owns `external_id` |
| SCIM Bridge | Intermediary SCIM server — owns `scim_id`, translates to target API |
| Brivo | Target system — receives provisioning actions, owns `target_id` |

## Components

| Component | Responsibility | Detail |
|---|---|---|
| SCIM Bridge | Translate SCIM 2.0 operations to target API calls | [scim-server.md](scim-server.md) |
| Mock Brivo Client | Simulate Brivo API with configurable failure modes | [brivo-mock.md](brivo-mock.md) |
| Rate Limiter | Enforce target request rate limit | [rate-limiter.md](rate-limiter.md) |
| Saga Orchestrator | Coordinate multi-step operations with rollback | [saga.md](saga.md) |
| PostgreSQL | Persistent store: ID mappings + provisioning audit trail | [database.md](database.md) |
| Redis | Cache layer for hot ID lookups | [redis.md](redis.md) |

## Constraints

- Target system enforces a rate limit — enforce at client layer, never drop under normal load
- Target responses may be partial/incomplete — handle gracefully
- All operations must be **idempotent** and retry-safe
- Multi-step operations must define forward + compensating (rollback) actions

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
