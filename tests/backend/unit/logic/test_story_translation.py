"""StoryService.get_story_in_language: when the cache is used, when Google
is called, and what gets saved. No database and no real Google calls."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from Backend.Logic.domain.story import Story, StoryStatus
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.exceptions import NotFoundError, TranslationUnavailableError
from Backend.Logic.story_service import StoryService

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


class FakeStoryRepository:
    def __init__(self):
        self.stories = {}
        self.translations = {}
        self.saved = []

    def get(self, story_id):
        return self.stories.get(story_id)

    def get_translation(self, story_id, language):
        return self.translations.get((story_id, language))

    def save_translation(self, story_id, language, *, title, summary, context):
        row = StoryTranslation(story_id, language, title, summary, context, updated_at=NOW)
        self.translations[(story_id, language)] = row
        self.saved.append(row)
        return row


class FakeTranslator:
    """Prefixes every text with EN: so tests can see what was translated."""

    def __init__(self, error=None):
        self.calls = []
        self.error = error

    def translate(self, texts, *, source, target):
        self.calls.append((list(texts), source, target))
        if self.error:
            raise self.error
        return [f"EN:{text}" for text in texts]


@pytest.fixture
def repo():
    return FakeStoryRepository()


@pytest.fixture
def translator():
    return FakeTranslator()


@pytest.fixture
def service(repo, translator):
    return StoryService(stories=repo, articles=None, tags=None, translator=translator)


def add_story(repo, *, title="Titel", summary="Samenvatting", context="Context", updated=NOW):
    story = Story(
        id=uuid4(), title=title, summary=summary, context=context,
        status=StoryStatus.published, first_published_at=None, last_updated_at=updated,
    )
    repo.stories[story.id] = story
    return story


def add_translation(repo, story, *, title="EN:old title", summary="EN:old summary",
                    context="EN:old context", updated=NOW + timedelta(minutes=1)):
    repo.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", title, summary, context, updated_at=updated,
    )


@pytest.mark.parametrize("language", [None, "nl", "NL", "de"])
def test_original_story_without_translating(service, repo, translator, language):
    story = add_story(repo)

    result = service.get_story_in_language(story.id, language)

    assert result == story
    assert translator.calls == []
    assert repo.saved == []


def test_first_request_translates_all_fields_in_one_call_and_saves(service, repo, translator):
    story = add_story(repo)

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls == [(["Titel", "Samenvatting", "Context"], "nl", "en")]
    assert (result.title, result.summary, result.context) == (
        "EN:Titel", "EN:Samenvatting", "EN:Context",
    )
    assert repo.saved[0].language == "en"
    assert repo.saved[0].title == "EN:Titel"


def test_language_from_profile_is_normalised(service, repo, translator):
    story = add_story(repo)

    service.get_story_in_language(story.id, " EN ")

    assert translator.calls[0][2] == "en"


def test_cached_translation_is_used_without_calling_google(service, repo, translator):
    story = add_story(repo)
    add_translation(repo, story)

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls == []
    assert result.title == "EN:old title"
    assert result.context == "EN:old context"


def test_second_request_hits_the_cache(service, repo, translator):
    story = add_story(repo)

    service.get_story_in_language(story.id, "en")
    service.get_story_in_language(story.id, "en")

    assert len(translator.calls) == 1


def test_empty_summary_is_not_sent_and_stays_empty(service, repo, translator):
    story = add_story(repo, summary=None)

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls[0][0] == ["Titel", "Context"]
    assert result.summary is None
    assert repo.saved[0].summary is None


def test_story_changed_after_translation_translates_everything_again(service, repo, translator):
    story = add_story(repo, updated=NOW)
    add_translation(repo, story, updated=NOW - timedelta(hours=1))

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls[0][0] == ["Titel", "Samenvatting", "Context"]
    assert result.title == "EN:Titel"


def test_only_the_field_that_was_missing_is_translated(service, repo, translator):
    # The summary got generated after the story was translated, without the
    # story counting as changed: only the summary costs characters.
    story = add_story(repo)
    add_translation(repo, story, summary=None)

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls[0][0] == ["Samenvatting"]
    assert result.title == "EN:old title"
    assert result.summary == "EN:Samenvatting"
    assert repo.saved[0].context == "EN:old context"


def test_old_translated_text_is_not_shown_when_the_story_has_none(service, repo, translator):
    story = add_story(repo, summary=None)
    add_translation(repo, story)

    result = service.get_story_in_language(story.id, "en")

    assert translator.calls == []
    assert result.summary is None


def test_google_failure_raises_and_saves_nothing(repo):
    service = StoryService(
        stories=repo, articles=None, tags=None,
        translator=FakeTranslator(error=TranslationUnavailableError("quota")),
    )
    story = add_story(repo)

    with pytest.raises(TranslationUnavailableError):
        service.get_story_in_language(story.id, "en")

    assert repo.saved == []


def test_no_translator_configured_raises_only_when_needed(repo):
    service = StoryService(stories=repo, articles=None, tags=None)
    cached = add_story(repo)
    add_translation(repo, cached)
    uncached = add_story(repo)

    assert service.get_story_in_language(cached.id, "en").title == "EN:old title"
    with pytest.raises(TranslationUnavailableError):
        service.get_story_in_language(uncached.id, "en")


def test_unknown_story_is_not_found(service, translator):
    with pytest.raises(NotFoundError):
        service.get_story_in_language(uuid4(), "en")

    assert translator.calls == []
