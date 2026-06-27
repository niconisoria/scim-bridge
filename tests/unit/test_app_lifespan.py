import pytest

from app.brivo.client import BrivoClient


async def test_lifespan_sets_brivo_client():
    from main import app, lifespan

    async with lifespan(app):
        assert isinstance(app.state.brivo_client, BrivoClient)
