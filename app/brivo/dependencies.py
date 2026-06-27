from fastapi import Request

from app.brivo.client import BrivoClient


def get_client(request: Request) -> BrivoClient:
    return request.app.state.brivo_client
