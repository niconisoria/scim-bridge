# Infra

Docker Compose topology for local development and integration testing.

## Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `app` | `./Dockerfile` | `8000` | SCIM Bridge (FastAPI + Uvicorn) |
| `mock-brivo` | `./Dockerfile.brivo` | `8001` | Mock Brivo API |
| `redis` | `redis:7-alpine` | `6379` | Shared state — AOF persistence required (`--appendonly yes`) |

`app` depends on `redis` and `mock-brivo` with `condition: service_healthy`. `mock-brivo` has no dependencies.

> Redis data loss = all `scim_id ↔ brivo_id` mappings lost. Full re-sync from Brivo required. AOF persistence is non-negotiable.

## Docker Compose Config Notes

### Redis — AOF persistence
```yaml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 3s
    retries: 5
```

### mock-brivo healthcheck
```yaml
mock-brivo:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
    interval: 5s
    timeout: 3s
    retries: 5
```

### app depends_on
```yaml
app:
  depends_on:
    redis:
      condition: service_healthy
    mock-brivo:
      condition: service_healthy
```

## Environment Variables

| Variable | Service | Description |
|---|---|---|
| `SCIM_BEARER_TOKEN` | app | Bearer token Okta sends |
| `REDIS_URL` | app | `redis://redis:6379` |
| `BRIVO_BASE_URL` | app | `http://mock-brivo:8001` |
| `BRIVO_RATE_LIMIT` | app, mock-brivo | Requests/sec limit (default `20`) |
| `BRIVO_ERROR_RATE` | mock-brivo | Simulated failure rate 0–1 (default `0.1`) |
| `BRIVO_LATENCY_MS` | mock-brivo | Max simulated latency in ms (default `300`) |
| `SCIM_BASE_URL` | app | Base URL for `meta.location` (e.g. `http://localhost:8000`) |

All vars in `.env` (not committed). Template at `.env.example`.
