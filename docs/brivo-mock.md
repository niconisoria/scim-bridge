# Mock Brivo Client

Standalone FastAPI service at `http://mock-brivo:8001`. Simulates the real Brivo Access API (`https://api.brivo.com/v1/api`) — it is independent of the SCIM bridge and has no knowledge of SCIM, Okta, or provisioning concepts. Implements only the endpoints the bridge calls; other real Brivo endpoints (credentials, photos, custom fields, access points) are out of scope.

## Authentication (real API)

Real Brivo requires two headers on all calls:
- `api-key: {your-api-key}` — from the Brivo developer portal
- `Authorization: bearer {access_token}` — OAuth 2.0 authorization code flow
- `Content-type: application/json` — required on all write requests

Mock accepts any `api-key` header value — no token flow simulated.

## Endpoints

### Users

| Method | Path | Operation |
|---|---|---|
| `GET` | `/v1/api/users` | List users |
| `POST` | `/v1/api/users` | Create user |
| `GET` | `/v1/api/users/{userId}` | Get user |
| `PUT` | `/v1/api/users/{userId}` | Update user |
| `DELETE` | `/v1/api/users/{userId}` | Delete user |
| `GET` | `/v1/api/users/{userId}/groups` | List user's groups |

### Groups

| Method | Path | Operation |
|---|---|---|
| `GET` | `/v1/api/groups` | List groups |
| `POST` | `/v1/api/groups` | Create group |
| `GET` | `/v1/api/groups/{groupId}` | Get group |
| `PUT` | `/v1/api/groups/{groupId}` | Update group |
| `DELETE` | `/v1/api/groups/{groupId}` | Delete group |
| `GET` | `/v1/api/groups/{groupId}/users` | List users in group |
| `PUT` | `/v1/api/groups/{groupId}/users/{userId}` | Add user to group |
| `DELETE` | `/v1/api/groups/{groupId}/users/{userId}` | Remove user from group |

## Resource Schemas

### User (Brivo)
```json
{
  "id": 12345,
  "externalId": "any-external-ref",
  "firstName": "John",
  "lastName": "Doe",
  "emails": [{ "address": "john@example.com", "type": "work" }],
  "phoneNumbers": [{ "number": "+15550001234", "type": "mobile" }],
  "suspended": false,
  "created": "2024-01-01T00:00:00Z",
  "updated": "2024-01-01T00:00:00Z"
}
```

`externalId` is Brivo's own field for referencing the user in an external system — it is set by the API caller. The bridge never sets this field; `externalId` is a bridge-internal concept only. `POST /users` returns `200` (not `201`) on success.

### Group (Brivo)
```json
{
  "id": 99,
  "name": "Engineering",
  "keypadUnlock": false,
  "immuneToAntipassback": false,
  "antipassbackResetTime": 0
}
```

`name` max 35 characters. Groups have no `externalId` field in the Brivo API.

### Paginated List Response
```json
{
  "data": [...],
  "offset": 0,
  "pageSize": 20,
  "count": 42
}
```

Query params: `offset` (default `0`), `pageSize` (default `20`, max `100`).

## Error Codes

| Code | When |
|---|---|
| `200` | Success with body (including creates — Brivo returns 200, not 201) |
| `204` | Success with no body (delete, group member assignment/removal) |
| `400` | Invalid input (e.g., group name > 35 chars) |
| `403` | Forbidden |
| `404` | Resource not found |
| `429` | Rate limit exceeded (simulated — not documented in real Brivo API) |
| `503` | Service unavailable (simulated) |

**Error response body:**
```json
{ "code": 404, "message": "Resource not found" }
```

### `GET /users/{userId}/groups` response

Used by the bridge's Delete User saga to fetch group memberships before removal.

```json
{ "count": 2, "data": [{ "id": 99, "name": "Engineering" }] }
```

## Seed Data

On startup, one user is pre-inserted into the in-memory store for local dev convenience:

```json
{ "id": 1, "externalId": "seed-user-1", "firstName": "Seed", "lastName": "User",
  "emails": [{ "address": "seed@example.com", "type": "work" }] }
```

The counter starts at 1, so the next created user gets id=2. The seed is reset on every restart.

## Behavior Simulation

| Behavior | Default | Env var |
|---|---|---|
| Latency | Random 50–300ms per request | `BRIVO_LATENCY_MS` |
| Error rate | 10% → `500` or `503` | `BRIVO_ERROR_RATE` |
| Partial responses | `GET` may omit `phoneNumbers` | — |
| Rate limit signal | Returns `429` when > 20 req/sec (simulated threshold) | `BRIVO_RATE_LIMIT` |

Partial responses are deterministic per `userId` for reproducible test scenarios.

## References

| Resource | URL |
|---|---|
| API docs home | https://apidocs.brivo.com |
| Access API overview (auth, pagination, errors) | https://apidocs.brivo.com/access/api-overview.md |
| Endpoint index | https://apidocs.brivo.com/access/access-api-context.yaml |
| User endpoints (OpenAPI 3.1) | https://apidocs.brivo.com/access/references/user.yaml |
| Group endpoints (OpenAPI 3.1) | https://apidocs.brivo.com/access/references/group.yaml |
