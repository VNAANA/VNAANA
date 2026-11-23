"""HTTP contract check for GET /tags without a database."""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

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
    # TestClient runs ASGI in a separate thread, even if E2E tooling owns a loop.
    with TestClient(app) as client:
        response = client.get("/tags")
    assert response.status_code == 200
    assert response.json() == [{"id": str(politics.id), "name": "Politics"}]
