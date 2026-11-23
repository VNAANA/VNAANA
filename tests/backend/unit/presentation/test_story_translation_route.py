"""GET /stories/{id}: which language gets asked for and how a failed
translation reaches the client. No database, Supabase or Google calls."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.exceptions import TranslationUnavailableError
from Backend.main import app
from Backend.Presentation.auth import OptionalSubject, get_optional_subject
from Backend.Presentation.dependencies import get_story_service, get_user_service


def story_details(story_id, title="Titel"):
    return StoryDetails(
        id=story_id, title=title, summary=None, context="Context",
        status=StoryStatus.published, first_published_at=None,
        last_updated_at=datetime(2026, 11, 19, tzinfo=timezone.utc),
    )


@pytest.fixture
def context():
    stories, users = Mock(), Mock()
    state = SimpleNamespace(subject=None, stories=stories, users=users)
    app.dependency_overrides[get_story_service] = lambda: stories
    app.dependency_overrides[get_user_service] = lambda: users
    app.dependency_overrides[get_optional_subject] = lambda: state.subject
    try:
        with TestClient(app) as client:
            state.client = client
            yield state
    finally:
        app.dependency_overrides.clear()


def test_signed_out_gets_the_original_language(context):
    story_id = uuid4()
    context.users.get_preferred_language.return_value = None
    context.stories.get_story_in_language.return_value = story_details(story_id)

    response = context.client.get(f"/stories/{story_id}")

    assert response.status_code == 200
    context.users.get_preferred_language.assert_called_once_with(None)
    context.stories.get_story_in_language.assert_called_once_with(story_id, None)


def test_signed_in_uses_the_profile_language(context):
    story_id = uuid4()
    context.subject = uuid4()
    context.users.get_preferred_language.return_value = "en"
    context.stories.get_story_in_language.return_value = story_details(story_id, title="Title")

    response = context.client.get(f"/stories/{story_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Title"
    context.users.get_preferred_language.assert_called_once_with(context.subject)
    context.stories.get_story_in_language.assert_called_once_with(story_id, "en")


def test_failed_translation_is_a_503(context):
    context.users.get_preferred_language.return_value = "en"
    context.stories.get_story_in_language.side_effect = TranslationUnavailableError(
        "Translation quota exceeded, try again later"
    )

    response = context.client.get(f"/stories/{uuid4()}")

    assert response.status_code == 503
    assert response.json() == {"detail": "Translation quota exceeded, try again later"}


def test_for_you_route_is_still_matched_before_the_story_id(context):
    response = context.client.get("/stories/for-you")

    # Not a 422 from parsing "for-you" as a story id.
    assert response.status_code != 422


def test_no_token_means_anonymous_without_calling_supabase():
    # Through a real request instead of asyncio.run(): after the E2E tests,
    # Playwright keeps an event loop running in this thread and asyncio.run()
    # refuses to start a second one. TestClient runs the app in its own thread.
    probe = FastAPI()

    @probe.get("/whoami")
    def whoami(subject: OptionalSubject):
        return {"subject": subject}

    with patch("Backend.Presentation.auth._verify_token") as verify:
        with TestClient(probe) as client:
            response = client.get("/whoami")

    assert response.status_code == 200
    assert response.json() == {"subject": None}
    verify.assert_not_called()


def test_preferred_language_comes_from_the_profile():
    from Backend.Logic.user_service import UserService

    subject = uuid4()
    repo = Mock()
    repo.get_by_identity.side_effect = lambda provider, sub: (
        SimpleNamespace(language="en") if sub == str(subject) else None
    )
    service = UserService(users=repo, tags=None, events=None, stories=None, articles=None, algorithm=None)

    assert service.get_preferred_language(subject) == "en"
    assert service.get_preferred_language(uuid4()) is None
    assert service.get_preferred_language(None) is None
