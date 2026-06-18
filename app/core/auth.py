import hmac
from uuid import uuid4

import structlog.contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.errors import scim_error

_DISCOVERY_PREFIXES = (
    "/scim/v2/ServiceProviderConfig",
    "/scim/v2/Schemas",
    "/scim/v2/ResourceTypes",
)


class BearerTokenMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=str(uuid4()))

        if not any(request.url.path.startswith(p) for p in _DISCOVERY_PREFIXES):
            auth = request.headers.get("Authorization", "")
            token = auth[7:].strip() if auth.startswith("Bearer ") else ""
            if not hmac.compare_digest(
                token.encode(), settings.scim_bearer_token.encode()
            ):
                return scim_error(401, "Unauthorized")

        response = await call_next(request)
        response.headers["Content-Type"] = "application/scim+json; charset=UTF-8"
        return response
