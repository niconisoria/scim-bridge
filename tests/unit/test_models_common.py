import pytest

from app.models.common import ListResponse, PatchOp, PatchRequest, ScimError, ScimMeta


def test_scim_meta_all_optional():
    m = ScimMeta()
    assert m.resourceType is None
    assert m.version is None


def test_list_response_empty():
    lr = ListResponse[dict](totalResults=0, itemsPerPage=0)
    assert lr.Resources == []
    assert lr.totalResults == 0
    assert lr.schemas == ["urn:ietf:params:scim:api:messages:2.0:ListResponse"]


def test_list_response_non_empty():
    lr = ListResponse[dict](totalResults=1, itemsPerPage=1, Resources=[{"id": "a"}])
    assert len(lr.Resources) == 1
    assert lr.startIndex == 1


def test_patch_op_normalizes_lowercase():
    op = PatchOp(op="Replace", path="active", value=False)
    assert op.op == "replace"


def test_patch_op_uppercase_add():
    op = PatchOp(op="ADD", value=[{"value": "123"}])
    assert op.op == "add"


def test_patch_request_schema():
    req = PatchRequest(Operations=[{"op": "replace", "path": "active", "value": True}])
    assert req.schemas == ["urn:ietf:params:scim:api:messages:2.0:PatchOp"]
    assert len(req.Operations) == 1
    assert req.Operations[0].op == "replace"


def test_scim_error_status_is_string():
    err = ScimError(status="404", detail="Not found")
    assert isinstance(err.status, str)
    assert err.status == "404"
    assert err.scimType is None
    assert err.schemas == ["urn:ietf:params:scim:api:messages:2.0:Error"]


def test_scim_error_with_scim_type():
    err = ScimError(status="409", detail="Already exists", scimType="uniqueness")
    assert err.scimType == "uniqueness"
