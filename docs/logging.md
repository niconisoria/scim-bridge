# Structured Logging

`structlog` with JSON renderer. All output to stdout.

## Request Logging

Uvicorn access logs are suppressed (`--no-access-log`). Instead, `RequestLoggingMiddleware` in `app/core/logging.py` logs every HTTP request through structlog:

```json
{"level": "info", "timestamp": "...", "event": "http.request", "method": "POST", "path": "/scim/v2/Users", "status": 201}
```

`configure_logging()` is called inside the FastAPI `lifespan` context manager, before any requests are served. Mock Brivo uses the same pattern with `_configure_logging()` and `_RequestLoggingMiddleware` (excludes `/health`).

If `call_next` raises (unhandled exception escaping route + exception handlers), middleware logs `http.error` with `error` field and re-raises:

```json
{"event": "http.error", "method": "GET", "path": "/scim/v2/Users/123", "error": "503: Simulated error", "level": "error", "timestamp": "..."}
```

## correlation_id Propagation

`correlation_id` is a UUID v4 generated per incoming SCIM request by the auth middleware. It propagates through all downstream calls via `structlog.contextvars`:

1. Middleware: `structlog.contextvars.bind_contextvars(correlation_id=str(uuid4()))`
2. All `structlog.get_logger().info(...)` calls in the same async context inherit it automatically
3. Passed to Brivo HTTP calls as `X-Correlation-ID` request header (for mock log correlation)
4. Saga steps read it from contextvars — no explicit parameter passing needed

`structlog.contextvars.clear_contextvars()` called at request teardown to prevent leakage between requests.

## Base Fields (every entry)

| Field | Description |
|---|---|
| `timestamp` | ISO 8601 UTC |
| `level` | `info` / `warning` / `error` |
| `correlation_id` | UUID per incoming SCIM request; propagated through saga and Brivo calls |
| `event` | Short description |

## Event-Specific Fields

### SCIM Request
`method`, `path`, `scim_id`, `operation`, `duration_ms`, `status_code`

### Brivo Call
`brivo_endpoint`, `brivo_id`, `attempt`, `duration_ms`, `status_code`, `error`

### Saga Step
`saga_id`, `step_index`, `action` (`forward` / `rollback`), `status`, `error`

### Rate Limiter
`wait_ms`

## Log Levels

| Level | When |
|---|---|
| `info` | Normal operations, saga completions |
| `warning` | Brivo `429`, partial response received, retry attempt |
| `error` | Step failure, saga rollback triggered, unrecoverable step |
