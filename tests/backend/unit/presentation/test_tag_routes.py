"""HTTP contract check for GET /tags without a database."""

import asyncio
import json
import uuid

from fastapi import FastAPI

from Backend.Logic.domain.tag import Tag
from Backend.Logic.tag_service import TagService
from Backend.Presentation.dependencies import get_tag_service
from Backend.Presentation.routers.tags import router


class FakeTagRepository:
    def __init__(self, tags: list[Tag]):
        self._tags = tags

    def list_all(self) -> list[Tag]:
        return self._tags


def test_list_tags_returns_ids_and_names_without_authentication():
    politics = Tag(id=uuid.uuid4(), name="Politics")
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_tag_service] = lambda: TagService(FakeTagRepository([politics]))
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": "/tags",
        "raw_path": b"/tags", "root_path": "", "query_string": b"",
        "headers": [], "server": ("testserver", 80), "client": ("testclient", 12345),
    }
    asyncio.run(app(scope, receive, send))

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
    assert start["status"] == 200
    assert json.loads(body) == [{"id": str(politics.id), "name": "Politics"}]
