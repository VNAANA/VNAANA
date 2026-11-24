"""GET /stories?tag_id=…: one or several tags, passed on to the service."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.domain.story import StoryStatus
from Backend.Presentation import dependencies
from Backend.Presentation.error_handlers import register_error_handlers
from Backend.Presentation.routers.stories import router


@pytest.fixture
def service():
    service = Mock()
    service.list_stories.return_value = []
    return service


@pytest.fixture
def client(service):
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[dependencies.get_story_service] = lambda: service
    return TestClient(app)


def sent_tag_ids(service):
    return service.list_stories.call_args.kwargs["tag_ids"]


def test_without_tags_no_tag_filter_is_sent(client, service):
    assert client.get("/stories").status_code == 200

    assert sent_tag_ids(service) is None
    assert service.list_stories.call_args.kwargs["status"] == StoryStatus.published


def test_a_single_tag_still_works(client, service):
    tag = uuid4()

    assert client.get("/stories", params={"tag_id": str(tag)}).status_code == 200

    assert sent_tag_ids(service) == [tag]


def test_repeated_tag_id_sends_every_tag(client, service):
    tags = [uuid4(), uuid4(), uuid4()]

    response = client.get("/stories", params=[("tag_id", str(tag)) for tag in tags])

    assert response.status_code == 200
    assert sent_tag_ids(service) == tags


def test_an_invalid_tag_id_is_rejected(client, service):
    assert client.get("/stories", params={"tag_id": "not-a-uuid"}).status_code == 422
    service.list_stories.assert_not_called()
