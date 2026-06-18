from fastapi.responses import JSONResponse

_SCIM_ERROR_SCHEMA = "urn:ietf:params:scim:api:messages:2.0:Error"
_SCIM_CONTENT_TYPE = "application/scim+json; charset=UTF-8"


def scim_error(status: int, detail: str, scim_type: str | None = None) -> JSONResponse:
    body: dict = {
        "schemas": [_SCIM_ERROR_SCHEMA],
        "status": str(status),
        "detail": detail,
    }
    if scim_type is not None:
        body["scimType"] = scim_type
    return JSONResponse(
        content=body,
        status_code=status,
        headers={"Content-Type": _SCIM_CONTENT_TYPE},
    )
