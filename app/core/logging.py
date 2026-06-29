import json

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        logger_factory=structlog.PrintLoggerFactory(),
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        body = None
        if request.method in ("POST", "PUT", "PATCH"):
            raw = await request.body()
            if raw:
                try:
                    body = json.loads(raw)
                except Exception:
                    body = raw.decode(errors="replace")
        try:
            response = await call_next(request)
        except Exception as exc:
            get_logger().error("http.error", method=request.method, path=request.url.path, body=body, error=str(exc))
            raise
        get_logger().info("http.request", method=request.method, path=request.url.path, body=body, status=response.status_code)
        return response


get_logger = structlog.get_logger
