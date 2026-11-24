"""StoryService.translate_story (the post's Translate button) and
get_story_in_language: when Google is called, what gets saved in
story_translations, and what the user gets back. No database and no real
Google calls."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from Backend.Logic.domain.article import Article, ArticleProvider
from Backend.Logic.domain.story import Story, StoryCard, StoryStatus
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.exceptions import NotFoundError, TranslationUnavailableError
from Backend.Logic.story_service import StoryService

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=1)
# When the fake saves a translation; like the database's now(), after every story update.
SAVED_AT = NOW + timedelta(days=1)


class FakeStoryRepository:
    def __init__(self):
        self.cards = {}
        self.translations = {}
        self.saved = []

    def get(self, story_id):
        card = self.cards.get(story_id)
        if card is None:
            return None
        # get() returns the plain story; to_cards adds the lead article.
        return Story(
            id=card.id, title=card.title, summary=card.summary, context=card.context,
            status=card.status, first_published_at=None, last_updated_at=card.last_updated_at,
        )

    def to_cards(self, stories):
        return [self.cards[story.id] for story in stories]

    def get_translation(self, story_id, language):
        return self.translations.get((story_id, language))

    def save_translation(self, story_id, language, *, title, summary, context,
                         description=None):
        row = StoryTranslation(
            story_id, language, title, summary, context, updated_at=SAVED_AT,
            description=description,
        )
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


def article(description="Beschrijving"):
    return Article(
        id=uuid4(),
        provider_id=uuid4(),
        provider=ArticleProvider(uuid4(), "NOS", "nos.nl", "NL", "verified"),
        canonical_url=f"https://nos.nl/{uuid4()}",
        title="Artikeltitel",
        description=description,
        content=None,
        is_scraped=False,
        author=None,
        language="nl",
        published_at=None,
        first_seen_at=NOW,
        last_seen_at=NOW,
    )


def add_story(repo, *, title="Titel", summary="Samenvatting", context="Context",
              description="Beschrijving", lead="default", updated=NOW):
    card = StoryCard(
        id=uuid4(), title=title, summary=summary, context=context,
        status=StoryStatus.published, first_published_at=None, last_updated_at=updated,
        lead_article=article(description) if lead == "default" else lead,
    )
    repo.cards[card.id] = card
    return card


def add_translation(repo, story, *, title="EN:old title", summary="EN:old summary",
                    context="EN:old context", description="EN:old description",
                    updated=LATER):
    repo.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", title, summary, context, updated_at=updated,
        description=description,
    )


def texts(card):
    return (card.title, card.summary, card.context, card.lead_article and card.lead_article.description)


# ---- translate_story: the Translate button ----


def test_everything_goes_to_google_in_one_call_and_is_saved(service, repo, translator):
    story = add_story(repo)

    result = service.translate_story(story.id, "en")

    assert translator.calls == [
        (["Titel", "Samenvatting", "Context", "Beschrijving"], "nl", "en")
    ]
    assert texts(result) == ("EN:Titel", "EN:Samenvatting", "EN:Context", "EN:Beschrijving")
    assert result.translated_into == "en"
    saved = repo.saved[0]
    assert (saved.language, saved.title, saved.description) == ("en", "EN:Titel", "EN:Beschrijving")


def test_the_rest_of_the_card_is_kept(service, repo):
    story = add_story(repo)

    result = service.translate_story(story.id, "en")

    assert result.id == story.id
    assert result.lead_article.id == story.lead_article.id
    assert result.lead_article.title == "Artikeltitel"


def test_language_from_profile_is_normalised(service, repo, translator):
    story = add_story(repo)

    service.translate_story(story.id, " EN ")

    assert translator.calls[0][2] == "en"


@pytest.mark.parametrize("language", [None, "nl", "NL", "de"])
def test_nothing_to_translate_into_returns_the_original(service, repo, translator, language):
    story = add_story(repo)

    result = service.translate_story(story.id, language)

    assert result == story
    assert result.translated_into is None
    assert translator.calls == [] and repo.saved == []


def test_an_already_translated_story_does_not_call_google(service, repo, translator):
    story = add_story(repo)
    add_translation(repo, story)

    result = service.translate_story(story.id, "en")

    assert translator.calls == [] and repo.saved == []
    assert texts(result) == ("EN:old title", "EN:old summary", "EN:old context", "EN:old description")
    assert result.translated_into == "en"


def test_pressing_twice_calls_google_once(service, repo, translator):
    story = add_story(repo)

    service.translate_story(story.id, "en")
    service.translate_story(story.id, "en")

    assert len(translator.calls) == 1


def test_empty_fields_are_not_sent_and_stay_empty(service, repo, translator):
    story = add_story(repo, summary=None, description=None)

    result = service.translate_story(story.id, "en")

    assert translator.calls[0][0] == ["Titel", "Context"]
    assert result.summary is None
    assert result.lead_article.description is None
    assert (repo.saved[0].summary, repo.saved[0].description) == (None, None)
    assert result.translated_into == "en"


def test_a_story_without_lead_article(service, repo, translator):
    story = add_story(repo, lead=None)

    result = service.translate_story(story.id, "en")

    assert translator.calls[0][0] == ["Titel", "Samenvatting", "Context"]
    assert result.lead_article is None
    assert result.translated_into == "en"


def test_a_story_changed_after_translating_is_redone_with_its_description(
    service, repo, translator
):
    story = add_story(repo, updated=LATER + timedelta(hours=1))
    add_translation(repo, story)

    result = service.translate_story(story.id, "en")

    assert translator.calls[0][0] == ["Titel", "Samenvatting", "Context", "Beschrijving"]
    assert result.title == "EN:Titel"
    assert result.lead_article.description == "EN:Beschrijving"


def test_a_description_missing_from_the_translation_is_added(service, repo, translator):
    # Translated before descriptions were saved with the story.
    story = add_story(repo)
    add_translation(repo, story, description=None)

    result = service.translate_story(story.id, "en")

    assert translator.calls[0][0] == ["Beschrijving"]
    assert result.lead_article.description == "EN:Beschrijving"
    assert result.title == "EN:old title"
    assert repo.saved[0].description == "EN:Beschrijving"


def test_only_the_field_that_was_missing_is_translated(service, repo, translator):
    # The summary got generated after the story was translated, without the
    # story counting as changed: only the summary costs characters.
    story = add_story(repo)
    add_translation(repo, story, summary=None)

    result = service.translate_story(story.id, "en")

    assert translator.calls[0][0] == ["Samenvatting"]
    assert result.summary == "EN:Samenvatting"
    assert repo.saved[0].context == "EN:old context"
    assert repo.saved[0].description == "EN:old description"


def test_google_failure_raises_and_saves_nothing(repo):
    service = StoryService(
        stories=repo, articles=None, tags=None,
        translator=FakeTranslator(error=TranslationUnavailableError("quota")),
    )
    story = add_story(repo)

    with pytest.raises(TranslationUnavailableError):
        service.translate_story(story.id, "en")

    assert repo.saved == []


def test_no_translator_configured_raises_only_when_needed(repo):
    service = StoryService(stories=repo, articles=None, tags=None)
    translated = add_story(repo)
    add_translation(repo, translated)
    untranslated = add_story(repo)

    assert service.translate_story(translated.id, "en").title == "EN:old title"
    with pytest.raises(TranslationUnavailableError):
        service.translate_story(untranslated.id, "en")


def test_unknown_story_is_not_found(service, translator):
    with pytest.raises(NotFoundError):
        service.translate_story(uuid4(), "en")

    assert translator.calls == []


# ---- get_story_in_language: only what was saved ----


def test_get_story_uses_the_saved_translation(service, repo, translator):
    story = add_story(repo)
    add_translation(repo, story)

    result = service.get_story_in_language(story.id, "en")

    assert (result.title, result.summary, result.context) == (
        "EN:old title", "EN:old summary", "EN:old context",
    )
    assert translator.calls == []


def test_get_story_never_calls_google(service, repo, translator):
    story = add_story(repo)

    result = service.get_story_in_language(story.id, "en")

    assert result.title == "Titel"
    assert result.translated_into is None
    assert translator.calls == [] and repo.saved == []


@pytest.mark.parametrize("language", [None, "nl", "de"])
def test_get_story_in_the_original_language(service, repo, language):
    story = add_story(repo)
    add_translation(repo, story)

    assert service.get_story_in_language(story.id, language).title == "Titel"


def test_old_translated_text_is_not_shown_when_the_story_has_none(service, repo):
    story = add_story(repo, summary=None)
    add_translation(repo, story)

    assert service.get_story_in_language(story.id, "en").summary is None


def test_the_original_card_is_not_changed(service, repo):
    story = add_story(repo)
    before = replace(story)

    service.translate_story(story.id, "en")

    assert story == before
