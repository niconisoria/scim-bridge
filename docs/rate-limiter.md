# Rate Limiter

Enforces Brivo's 20 req/sec limit at the Brivo client layer. Requests queue rather than fail under normal load.

## Algorithm

Leaky bucket (`aiolimiter` implementation):
- At most 20 requests allowed within any 1-second window
- Requests are distributed evenly — no burst accumulation
- On every Brivo HTTP call: `async with limiter:` before sending
- If rate exceeded: caller `await`s until the next slot opens

## Implementation

`aiolimiter.AsyncLimiter(max_rate=20, time_period=1)` wraps every outbound Brivo call. Handles queueing within the process — callers `await` token acquisition.

`max_rate` reads from `BRIVO_RATE_LIMIT` env var (default `20`). Same value used by the mock's rate-limit signal.

## Brivo 429 Handling

On Brivo `429` response:
- Back off 1s, retry via `tenacity` (counts against rate limit budget)
- Bridge absorbs retry internally — does not propagate `429` to Okta while retries remain
- All tenacity attempts exhausted → propagate `429` to caller

## Behavior Under Load

- Requests never dropped — callers block on token acquisition
- On shutdown: in-flight requests complete, queued requests cancelled gracefully
