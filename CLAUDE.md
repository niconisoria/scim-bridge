# CLAUDE.md — scim-bridge

## Iron Laws

1. **Spec first** — no code without a spec file in `docs/specs/`.
2. **Test first** — write failing tests before implementation.
3. **Verify before done** — run the app and confirm the feature works end-to-end before closing a task.
4. **No secrets in code** — credentials/tokens go in `.env` (never committed).
5. **CLAUDE.md < 200 lines** — move detail into linked docs, not here.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.14 |
| Framework | FastAPI |
| Server | Uvicorn |
| Validation | Pydantic v2 |
| Settings | pydantic-settings |
| Database | PostgreSQL + SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic |
| Cache | Redis (redis-py asyncio) |
| HTTP client | httpx (AsyncClient) |
| Rate limiting | aiolimiter (token bucket) |
| Retries | tenacity |
| Logging | structlog |
| Testing | pytest + pytest-asyncio + httpx |
| Test mocks | pytest-postgresql + fakeredis + respx |
| Infra | Docker + Compose |

---

## Project Map

```
scim-bridge/
├── CLAUDE.md               ← you are here
├── main.py                 ← FastAPI app entry point
├── alembic/                ← migration scripts
│   └── versions/
├── docker-compose.yml
├── Dockerfile
├── docs/
│   ├── architecture.md     ← system design, components, constraints
│   └── specs/              ← one .md per feature (brainstorm → stories → flows → impl)
├── app/
│   ├── routers/            ← SCIM endpoints (users, groups)
│   ├── models/             ← Pydantic schemas (SCIM resources)
│   ├── services/           ← SCIM logic, saga orchestrator
│   ├── brivo/              ← Brivo client + rate limiter
│   ├── db/                 ← SQLAlchemy models, session, repositories
│   ├── redis/              ← cache layer, rate-limiter coordination
│   └── core/               ← config, auth middleware, error handlers, logging
├── tests/
│   ├── unit/
│   └── integration/
└── .env.example
```

---

## Roles

| Actor | Role | ID field |
|---|---|---|
| Okta (IdP) | Initiates provisioning | `external_id` |
| Bridge | SCIM intermediary | `scim_id` |
| Brivo (target) | Receives provisioning actions | `target_id` |

---

## Docs

- [docs/architecture.md](docs/architecture.md) — global system view, components, constraints
- [docs/database.md](docs/database.md) — schema, migrations, access patterns
- [docs/scim-server.md](docs/scim-server.md) — SCIM 2.0 endpoints, schemas, auth, field mapping
- [docs/brivo-mock.md](docs/brivo-mock.md) — mock Brivo API, failure simulation
- [docs/rate-limiter.md](docs/rate-limiter.md) — token bucket, Redis coordination, 429 handling
- [docs/saga.md](docs/saga.md) — saga state machine, all multi-step operations
- [docs/redis.md](docs/redis.md) — cache key inventory, TTL strategy, access patterns
- [docs/logging.md](docs/logging.md) — structlog fields, levels
- [docs/testing.md](docs/testing.md) — unit + integration test strategy
- [docs/infra.md](docs/infra.md) — Docker services, env vars
- [docs/specs/](docs/specs/) — feature specs (start here for any new work)
