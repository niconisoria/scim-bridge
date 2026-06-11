# Architecture

Automated identity lifecycle management from Okta into Brivo via SCIM 2.0.
Ensures reliability under rate limits, incomplete downstream data, and multi-step provisioning workflows.

## Flow

```mermaid
flowchart LR
    Okta -->|SCIM 2.0| Bridge["SCIM Bridge\n(FastAPI)"]
    Bridge --> Saga["Saga Orchestrator"]
    Saga -->|HTTP| Brivo["Mock Brivo Client"]
    Saga <-->|saga state| Redis
    Bridge <-->|ID mapping (persistent)| Redis
```

## Components

| Component | Responsibility | Detail |
|---|---|---|
| SCIM Bridge | Translate SCIM 2.0 operations to Brivo API calls | [scim-server.md](scim-server.md) |
| Mock Brivo Client | Simulate Brivo API with configurable failure modes | [brivo-mock.md](brivo-mock.md) |
| Rate Limiter | Enforce Brivo request rate limit | [rate-limiter.md](rate-limiter.md) |
| Saga Orchestrator | Coordinate multi-step operations with rollback | [saga.md](saga.md) |
| Redis | Shared state for all components | [redis.md](redis.md) |

## Constraints

- Brivo enforces a rate limit — enforce at client layer, never drop under normal load
- Brivo responses may be partial/incomplete — handle gracefully
- All operations must be **idempotent** and retry-safe
- Multi-step operations must define forward + compensating (rollback) actions

## Deliverables

| Deliverable | Doc |
|---|---|
| FastAPI SCIM server | [scim-server.md](scim-server.md) |
| Mock Brivo client | [brivo-mock.md](brivo-mock.md) |
| Rate limiter module | [rate-limiter.md](rate-limiter.md) |
| Saga orchestrator | [saga.md](saga.md) |
| Redis integration | [redis.md](redis.md) |
| Infra (Docker + Compose) | [infra.md](infra.md) |
| Testing strategy | [testing.md](testing.md) |
| Structured logging | [logging.md](logging.md) |
