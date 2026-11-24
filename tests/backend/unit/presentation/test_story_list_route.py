"""GET /stories: tag filter (tag_id, repeatable), title search (q) and paging."""

from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.domain.story import StoryStatus
from Backend.Logic.story_service import StoryService
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


def sent(service, name):
    return service.list_stories.call_args.kwargs[name]


# ---------- Tags ----------

def test_without_tags_no_tag_filter_is_sent(client, service):
    assert client.get("/stories").status_code == 200

    assert sent(service, "tag_ids") is None
    assert sent(service, "status") == StoryStatus.published


def test_a_single_tag_still_works(client, service):
    tag = uuid4()

    assert client.get("/stories", params={"tag_id": str(tag)}).status_code == 200

    assert sent(service, "tag_ids") == [tag]


def test_repeated_tag_id_sends_every_tag(client, service):
    tags = [uuid4(), uuid4(), uuid4()]

    response = client.get("/stories", params=[("tag_id", str(tag)) for tag in tags])

    assert response.status_code == 200
    assert sent(service, "tag_ids") == tags


def test_an_invalid_tag_id_is_rejected(client, service):
    assert client.get("/stories", params={"tag_id": "not-a-uuid"}).status_code == 422
    service.list_stories.assert_not_called()


# ---------- Search ----------

def test_search_without_tags_searches_every_story(client, service):
    assert client.get("/stories", params={"q": "flood"}).status_code == 200

    assert sent(service, "q") == "flood"
    assert sent(service, "tag_ids") is None


def test_search_with_tags_searches_only_those_tags(client, service):
    tags = [uuid4(), uuid4()]

    response = client.get("/stories", params=[("q", "flood"), *(("tag_id", str(tag)) for tag in tags)])

    assert response.status_code == 200
    assert sent(service, "q") == "flood"
    assert sent(service, "tag_ids") == tags


def test_search_longer_than_100_characters_is_rejected(client, service):
    assert client.get("/stories", params={"q": "a" * 101}).status_code == 422
    service.list_stories.assert_not_called()


def test_one_letter_search_is_a_400(client):
    # The real service decides what a valid search is; the route turns its error into a 400.
    repository = Mock()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[dependencies.get_story_service] = lambda: StoryService(repository, Mock(), Mock())

    response = TestClient(app).get("/stories", params={"q": "a"})

    assert response.status_code == 400
    repository.list.assert_not_called()


# ---------- Paging ----------

def test_default_page_is_the_first_20(client, service):
    client.get("/stories")

    assert sent(service, "limit") == 20
    assert sent(service, "offset") == 0


def test_limit_and_offset_are_passed_on_with_search_and_tags(client, service):
    tag = uuid4()

    response = client.get("/stories", params={"q": "flood", "tag_id": str(tag), "limit": 20, "offset": 40})

    assert response.status_code == 200
    assert sent(service, "limit") == 20
    assert sent(service, "offset") == 40


@pytest.mark.parametrize(
    "params",
    [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": "many"}],
)
def test_out_of_range_paging_is_rejected(client, service, params):
    assert client.get("/stories", params=params).status_code == 422
    service.list_stories.assert_not_called()
