# Infra

Docker Compose topology for local development and integration testing.

## Services

| Service | Image | Port | Notes |
|---|---|---|---|
| `app` | `./Dockerfile` | `8000` | SCIM Bridge (FastAPI + Uvicorn) |
| `mock-brivo` | `./Dockerfile.brivo` | `8001` | Simulates Brivo API; in-memory state is authoritative for tests |
| `redis` | `redis:7-alpine` | `6379` | ID mapping store + Brivo response cache |

`app` depends on `redis` and `mock-brivo` with `condition: service_healthy`. `mock-brivo` has no dependencies.

## Docker Compose Config Notes

### Redis

```yaml
redis:
  image: redis:7-alpine
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

`app` Settings uses `extra="ignore"` — mock-brivo-only vars (`BRIVO_ERROR_RATE`, `BRIVO_LATENCY_MS`) in a shared `.env` are silently ignored and do not cause a startup error.
