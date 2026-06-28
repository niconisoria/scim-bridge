from fastapi.responses import JSONResponse

from app.models.common import ScimError


class ScimBadRequest(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class ScimConflict(Exception):
    def __init__(self, detail: str = "Resource already exists") -> None:
        self.detail = detail
        super().__init__(detail)


class ScimNotFound(Exception):
    def __init__(self, detail: str = "Resource not found") -> None:
        self.detail = detail
        super().__init__(detail)


_SCIM_CONTENT_TYPE = "application/scim+json; charset=UTF-8"


def scim_error(status: int, detail: str, scim_type: str | None = None) -> JSONResponse:
    return JSONResponse(
        content=ScimError(
            status=str(status), detail=detail, scimType=scim_type
        ).model_dump(exclude_none=True),
        status_code=status,
        headers={"Content-Type": _SCIM_CONTENT_TYPE},
    )
