# Mock Brivo Client

Standalone FastAPI service at `http://mock-brivo:8001`. Mirrors the real Brivo Access API surface used by the SCIM bridge, with configurable failure modes. All calls from the bridge go through the rate-limited client interface (→ [rate-limiter.md](rate-limiter.md)).

## Authentication (real API)

Real Brivo requires OAuth 2.0 (`api-key` header + `Authorization: bearer {token}`). The mock accepts any `api-key` header value — no token flow needed.

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
  "externalId": "okta-user-id",
  "firstName": "John",
  "lastName": "Doe",
  "emails": [{ "address": "john@example.com" }],
  "phoneNumbers": [{ "number": "+15550001234" }],
  "suspended": false,
  "created": "2024-01-01T00:00:00Z",
  "updated": "2024-01-01T00:00:00Z"
}
```

### Group (Brivo)
```json
{
  "id": 99,
  "externalId": "okta-group-id",
  "name": "Engineering"
}
```

`name` max 35 characters.

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
| `200` | Success with body |
| `204` | Successful delete or assignment (no body) |
| `400` | Invalid input (e.g., group name > 35 chars) |
| `403` | Forbidden |
| `404` | Resource not found |
| `429` | Rate limit exceeded |
| `503` | Service unavailable (simulated) |

## Behavior Simulation

| Behavior | Default | Env var |
|---|---|---|
| Latency | Random 50–300ms per request | `BRIVO_LATENCY_MS` |
| Error rate | 10% → `500` or `503` | `BRIVO_ERROR_RATE` |
| Partial responses | `GET` may omit `phoneNumbers` | — |
| Rate limit signal | Returns `429` when > 20 req/sec | `BRIVO_RATE_LIMIT` |

Partial responses are deterministic per `userId` for reproducible test scenarios.

## References

| Resource | URL |
|---|---|
| API docs home | https://apidocs.brivo.com |
| Access API overview (auth, pagination, errors) | https://apidocs.brivo.com/access/api-overview.md |
| Endpoint index | https://apidocs.brivo.com/access/access-api-context.yaml |
| User endpoints (OpenAPI 3.1) | https://apidocs.brivo.com/access/references/user.yaml |
| Group endpoints (OpenAPI 3.1) | https://apidocs.brivo.com/access/references/group.yaml |
