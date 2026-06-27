from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/scim/v2", tags=["discovery"])

_SPC = {
    "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
    "patch": {"supported": True},
    "bulk": {"supported": False, "maxOperations": 0, "maxPayloadSize": 0},
    "filter": {"supported": True, "maxResults": 200},
    "changePassword": {"supported": False},
    "sort": {"supported": False},
    "etag": {"supported": True},
    "authenticationSchemes": [
        {
            "type": "oauthbearertoken",
            "name": "OAuth Bearer Token",
            "description": "Bearer token via Authorization header",
            "specUri": "https://www.rfc-editor.org/rfc/rfc6750",
            "primary": True,
        }
    ],
}

_RESOURCE_TYPES = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
    "totalResults": 2,
    "Resources": [
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "id": "User",
            "name": "User",
            "endpoint": "/Users",
            "schema": "urn:ietf:params:scim:schemas:core:2.0:User",
        },
        {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ResourceType"],
            "id": "Group",
            "name": "Group",
            "endpoint": "/Groups",
            "schema": "urn:ietf:params:scim:schemas:core:2.0:Group",
        },
    ],
}

_USER_SCHEMA = {
    "id": "urn:ietf:params:scim:schemas:core:2.0:User",
    "name": "User",
    "description": "User Account",
    "schemas": ["urn:ietf:params:scim:meta:schemas:core:2.0:Schema"],
    "attributes": [
        {
            "name": "userName",
            "type": "string",
            "multiValued": False,
            "required": True,
            "caseExact": False,
            "mutability": "readWrite",
            "returned": "default",
            "uniqueness": "server",
        },
        {
            "name": "name",
            "type": "complex",
            "multiValued": False,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "subAttributes": [
                {
                    "name": "givenName",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
                {
                    "name": "familyName",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
            ],
        },
        {
            "name": "displayName",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": False,
            "mutability": "readWrite",
            "returned": "default",
        },
        {
            "name": "active",
            "type": "boolean",
            "multiValued": False,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
        },
        {
            "name": "externalId",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": True,
            "mutability": "readWrite",
            "returned": "default",
        },
        {
            "name": "emails",
            "type": "complex",
            "multiValued": True,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "subAttributes": [
                {
                    "name": "value",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
                {
                    "name": "type",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
                {
                    "name": "primary",
                    "type": "boolean",
                    "multiValued": False,
                    "required": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
            ],
        },
        {
            "name": "phoneNumbers",
            "type": "complex",
            "multiValued": True,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "subAttributes": [
                {
                    "name": "value",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
                {
                    "name": "type",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
                {
                    "name": "primary",
                    "type": "boolean",
                    "multiValued": False,
                    "required": False,
                    "mutability": "readWrite",
                    "returned": "default",
                },
            ],
        },
    ],
}

_GROUP_SCHEMA = {
    "id": "urn:ietf:params:scim:schemas:core:2.0:Group",
    "name": "Group",
    "description": "Group",
    "schemas": ["urn:ietf:params:scim:meta:schemas:core:2.0:Schema"],
    "attributes": [
        {
            "name": "displayName",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": False,
            "mutability": "readWrite",
            "returned": "default",
        },
        {
            "name": "externalId",
            "type": "string",
            "multiValued": False,
            "required": False,
            "caseExact": True,
            "mutability": "readWrite",
            "returned": "default",
        },
        {
            "name": "members",
            "type": "complex",
            "multiValued": True,
            "required": False,
            "mutability": "readWrite",
            "returned": "default",
            "subAttributes": [
                {
                    "name": "value",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "immutable",
                    "returned": "default",
                },
                {
                    "name": "display",
                    "type": "string",
                    "multiValued": False,
                    "required": False,
                    "caseExact": False,
                    "mutability": "immutable",
                    "returned": "default",
                },
            ],
        },
    ],
}

_SCHEMAS = {
    "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
    "totalResults": 2,
    "Resources": [_USER_SCHEMA, _GROUP_SCHEMA],
}


@router.get("/ServiceProviderConfig")
async def service_provider_config() -> JSONResponse:
    return JSONResponse(content=_SPC)


@router.get("/ResourceTypes")
async def resource_types() -> JSONResponse:
    return JSONResponse(content=_RESOURCE_TYPES)


@router.get("/Schemas")
async def schemas() -> JSONResponse:
    return JSONResponse(content=_SCHEMAS)
