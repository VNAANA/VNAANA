"""Story routes and translation: which language gets asked for, the
Translate button's POST /stories/{id}/translation, and how a failed
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


def test_story_list_uses_the_profile_language(context):
    context.subject = uuid4()
    context.users.get_preferred_language.return_value = "en"
    context.stories.list_stories.return_value = []

    response = context.client.get("/stories?limit=5")

    assert response.status_code == 200
    context.users.get_preferred_language.assert_called_once_with(context.subject)
    assert context.stories.list_stories.call_args.kwargs["language"] == "en"


def test_story_list_signed_out_passes_no_language(context):
    context.users.get_preferred_language.return_value = None
    context.stories.list_stories.return_value = []

    assert context.client.get("/stories").status_code == 200
    context.users.get_preferred_language.assert_called_once_with(None)
    assert context.stories.list_stories.call_args.kwargs["language"] is None


# ---- POST /stories/{id}/translation: the Translate button ----


@pytest.fixture
def translate_context(context):
    from Backend.Presentation.auth import get_authenticated_subject

    context.subject = uuid4()
    context.profile = SimpleNamespace(id=uuid4(), language="en")
    context.users.get_authenticated_user.return_value = context.profile
    app.dependency_overrides[get_authenticated_subject] = lambda: context.subject
    return context


def story_card(story_id, title="Title", translated_into="en"):
    from Backend.Logic.domain.story import StoryCard

    return StoryCard(
        id=story_id, title=title, summary=None, context="Context",
        status=StoryStatus.published, first_published_at=None,
        last_updated_at=datetime(2026, 11, 24, tzinfo=timezone.utc),
        translated_into=translated_into,
    )


def test_translate_uses_the_profile_language_and_returns_the_card(translate_context):
    c = translate_context
    story_id = uuid4()
    c.stories.translate_story.return_value = story_card(story_id)

    response = c.client.post(f"/stories/{story_id}/translation")

    assert response.status_code == 200
    body = response.json()
    assert (body["id"], body["title"], body["translated_into"]) == (str(story_id), "Title", "en")
    c.users.get_authenticated_user.assert_called_once_with(c.subject)
    c.stories.translate_story.assert_called_once_with(story_id, "en")


def test_translate_needs_sign_in(context):
    response = context.client.post(f"/stories/{uuid4()}/translation")

    assert response.status_code == 401
    context.stories.translate_story.assert_not_called()


def test_failed_translation_is_a_503(translate_context):
    translate_context.stories.translate_story.side_effect = TranslationUnavailableError(
        "Translation quota exceeded, try again later"
    )

    response = translate_context.client.post(f"/stories/{uuid4()}/translation")

    assert response.status_code == 503
    assert response.json() == {"detail": "Translation quota exceeded, try again later"}


def test_translating_an_unknown_story_is_a_404(translate_context):
    from Backend.Logic.exceptions import NotFoundError

    story_id = uuid4()
    translate_context.stories.translate_story.side_effect = NotFoundError("Story", story_id)

    response = translate_context.client.post(f"/stories/{story_id}/translation")

    assert response.status_code == 404


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


# ---- GET /stories/for-you ----


@pytest.fixture
def feed_context(context):
    from Backend.Logic.domain.feed import Feed, FeedStatus, RankedStory
    from Backend.Logic.domain.story import StoryCard
    from Backend.Presentation.auth import get_authenticated_subject
    from Backend.Presentation.dependencies import get_algorithm_service

    context.subject = uuid4()
    context.algorithm = Mock()
    context.profile = SimpleNamespace(id=uuid4(), language="en")
    context.users.get_authenticated_user.return_value = context.profile

    raw = Feed(FeedStatus.available, [])
    cards = Feed(FeedStatus.available, [])
    translated = Feed(
        FeedStatus.available,
        [
            RankedStory(
                StoryCard(
                    id=uuid4(), title="Title", summary=None, context="Context",
                    status=StoryStatus.published, first_published_at=None,
                    last_updated_at=datetime(2026, 11, 24, tzinfo=timezone.utc),
                ),
                2.5,
            )
        ],
    )
    context.algorithm.get_feed.return_value = raw
    context.stories.with_cards.return_value = cards
    context.stories.with_feed_translations.return_value = translated
    context.feeds = SimpleNamespace(raw=raw, cards=cards, translated=translated)

    app.dependency_overrides[get_algorithm_service] = lambda: context.algorithm
    app.dependency_overrides[get_authenticated_subject] = lambda: context.subject
    return context


def test_for_you_shows_translations_in_the_profile_language(feed_context):
    c = feed_context

    response = c.client.get("/stories/for-you?limit=10&offset=20")

    assert response.status_code == 200
    assert response.json()["stories"][0]["story"]["title"] == "Title"
    c.users.get_authenticated_user.assert_called_once_with(c.subject)
    c.algorithm.get_feed.assert_called_once_with(c.profile.id, limit=10, offset=20)
    c.stories.with_cards.assert_called_once_with(c.feeds.raw)
    # The language comes from the profile that was already loaded, so no
    # second lookup through get_preferred_language.
    c.stories.with_feed_translations.assert_called_once_with(c.feeds.cards, "en")
    c.users.get_preferred_language.assert_not_called()


def test_for_you_without_a_profile_language_passes_none(feed_context):
    c = feed_context
    c.profile.language = None

    assert c.client.get("/stories/for-you").status_code == 200
    c.stories.with_feed_translations.assert_called_once_with(c.feeds.cards, None)


def test_for_you_never_calls_google(feed_context):
    """Through the real StoryService: an untranslated story stays Dutch."""
    from Backend.Logic.domain.feed import Feed, FeedStatus, RankedStory
    from Backend.Logic.domain.story import StoryCard
    from Backend.Logic.story_service import StoryService

    c = feed_context
    card = StoryCard(
        id=uuid4(), title="Titel", summary=None, context="Context",
        status=StoryStatus.published, first_published_at=None,
        last_updated_at=datetime(2026, 11, 24, tzinfo=timezone.utc),
    )
    repo = Mock()
    repo.get_translations.return_value = {}
    translator = Mock()
    translator.translate.side_effect = TranslationUnavailableError("offline")
    service = StoryService(stories=repo, articles=Mock(), tags=None, translator=translator)
    c.algorithm.get_feed.return_value = Feed(FeedStatus.available, [RankedStory(card, 1.0)])
    service.with_cards = lambda feed: feed
    app.dependency_overrides[get_story_service] = lambda: service

    response = c.client.get("/stories/for-you")

    assert response.status_code == 200
    assert response.json()["stories"][0]["story"]["title"] == "Titel"
    assert response.json()["stories"][0]["story"]["translated_into"] is None
    translator.translate.assert_not_called()
    repo.save_translation.assert_not_called()
