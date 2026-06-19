---
title: Mock Brivo User Endpoints
status: implemented
refs: [20260619184934_mock_brivo_skeleton.md, 20260618195155_brivo_models.md]
---

## Brainstorm

Task #16: add full user CRUD + list-user-groups to mock Brivo service.

Skeleton (#15) already has `GET /v1/api/users` (list stub), in-memory `users` dict, `next_id()`, auth middleware, and inline Pydantic models. This task fills in the remaining 5 user endpoints.

Scope: only user endpoints. Group CRUD and member management are #17. List-user-groups (`GET /users/{id}/groups`) is included here (used by Delete User saga) and needs a `group_members` store introduced now so #17 can populate it.

Constraints:
- `POST` returns 200 not 201 (Brivo quirk)
- `DELETE` returns 204 no body
- `BrivoUser` inline model missing `externalId` — add it
- `GET /users/{id}/groups` response shape: `{ "count": N, "data": [{ "id": N, "name": "..." }] }` — not full BrivoPage
- `name` field in group data is required for that response

Related: [Mock Brivo Skeleton](20260619184934_mock_brivo_skeleton.md)

## Story

As bridge developer, want complete mock Brivo user API, so bridge client can be tested end-to-end without real Brivo.

AC:
1. `POST /v1/api/users` creates user, returns 200 with full `BrivoUser` (including `externalId`)
2. `GET /v1/api/users/{userId}` returns user or 404
3. `PUT /v1/api/users/{userId}` replaces user fields, updates `updated` timestamp, returns 200
4. `DELETE /v1/api/users/{userId}` removes user, returns 204; 404 if not found
5. `GET /v1/api/users/{userId}/groups` returns `{ "count": N, "data": [{ "id": N, "name": "..." }] }`; 404 if user not found
6. All endpoints reject missing `api-key` header with 403
7. `BrivoUser` inline model includes `externalId: str | None = None`
8. `group_members: dict[int, set[int]]` added to in-memory store (group_id → user_ids); cleared on lifespan reset
9. Test file covers all 5 new endpoints + 404/403 cases

## Design

### Flow

```mermaid
flowchart LR
    A([request]) --> B{api-key?}
    B -- no --> C([403])
    B -- yes --> D{endpoint}
    D -- POST /users --> E[assign id+timestamps, store] --> F([200 BrivoUser])
    D -- GET /users/id --> G{exists?}
    G -- no --> H([404])
    G -- yes --> I([200 BrivoUser])
    D -- PUT /users/id --> J{exists?}
    J -- no --> H
    J -- yes --> K[merge fields, bump updated] --> L([200 BrivoUser])
    D -- DELETE /users/id --> M{exists?}
    M -- no --> H
    M -- yes --> N[del users[id]] --> O([204])
    D -- GET /users/id/groups --> P{user exists?}
    P -- no --> H
    P -- yes --> Q[scan group_members] --> R([200 count+data])
```

### Data

POST/PUT body: `BrivoUserIn` `{ firstName, lastName, emails?, phoneNumbers?, suspended?, externalId? }`

GET /users/{id}/groups response: `{ "count": int, "data": [{ "id": int, "name": str }] }`

### Modules

- `mock_brivo/main.py` — add `externalId: str | None = None` to `BrivoUser`; add `BrivoUserIn` input model; add `group_members: dict[int, set[int]]` store + clear in lifespan; implement 5 endpoints
- `tests/unit/test_mock_brivo_users.py` — new file; tests for all 5 endpoints + 404 + 403

[mock_brivo/main.py](mock_brivo/main.py) [tests/unit/test_mock_brivo_users.py](tests/unit/test_mock_brivo_users.py)

## Summary

Added 5 user endpoints to mock Brivo: POST/GET/PUT/DELETE /v1/api/users and GET /v1/api/users/{id}/groups. Added `BrivoUserIn` write model, `externalId` to `BrivoUser`, and `group_members` store for task #17 to populate. PUT uses Pydantic v2 `model_copy(update=...)`. List-user-groups scans `group_members` reverse-index at query time — no separate user→groups index needed.
