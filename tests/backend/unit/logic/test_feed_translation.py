"""StoryService.translate_feed: which feed text goes to Google, what gets
cached, and what the user sees when Google fails. No database and no real
Google calls."""

import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from Backend.Logic.domain.article import Article, ArticleProvider
from Backend.Logic.domain.article_translation import ArticleTranslation
from Backend.Logic.domain.feed import Feed, FeedStatus, RankedStory
from Backend.Logic.domain.story import StoryCard, StoryStatus
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.exceptions import TranslationUnavailableError
from Backend.Logic.story_service import StoryService

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=1)


class FakeStoryRepository:
    def __init__(self):
        self.translations = {}
        self.saved = []

    def get_translations(self, story_ids, language):
        return {
            story_id: self.translations[(story_id, language)]
            for story_id in story_ids
            if (story_id, language) in self.translations
        }

    def save_translation(self, story_id, language, *, title, summary, context):
        row = StoryTranslation(story_id, language, title, summary, context, updated_at=LATER)
        self.translations[(story_id, language)] = row
        self.saved.append(row)
        return row


class FakeArticleRepository:
    def __init__(self):
        self.translations = {}
        self.saved = []
        self.lookups = []

    def get_translations(self, article_ids, language):
        self.lookups.append(list(article_ids))
        return {
            article_id: self.translations[(article_id, language)]
            for article_id in article_ids
            if (article_id, language) in self.translations
        }

    def save_translation(self, article_id, language, *, source_description, description):
        row = ArticleTranslation(article_id, language, source_description, description, LATER)
        self.translations[(article_id, language)] = row
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
def stories():
    return FakeStoryRepository()


@pytest.fixture
def articles():
    return FakeArticleRepository()


@pytest.fixture
def translator():
    return FakeTranslator()


@pytest.fixture
def service(stories, articles, translator):
    return StoryService(stories=stories, articles=articles, tags=None, translator=translator)


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


def card(*, title="Titel", summary=None, context="Context", lead="default", updated=NOW):
    return StoryCard(
        id=uuid4(),
        title=title,
        summary=summary,
        context=context,
        status=StoryStatus.published,
        first_published_at=NOW,
        last_updated_at=updated,
        lead_article=article() if lead == "default" else lead,
    )


def feed(*cards):
    return Feed(FeedStatus.available, [RankedStory(c, 1.0) for c in cards])


def texts_of(result):
    return [
        (r.story.title, r.story.context, r.story.lead_article and r.story.lead_article.description)
        for r in result.stories
    ]


@pytest.mark.parametrize("language", [None, "nl", "NL", "de"])
def test_original_language_is_returned_untouched(service, translator, language):
    original = feed(card())

    assert service.translate_feed(original, language) is original
    assert translator.calls == []


def test_a_feed_without_stories_calls_nothing(service, translator, articles):
    locked = Feed(FeedStatus.locked)

    assert service.translate_feed(locked, "en") is locked
    assert translator.calls == []
    assert articles.lookups == []


def test_a_cold_page_is_translated_in_one_call_and_cached(service, translator, stories, articles):
    first = card(title="Titel 1", summary="Samenvatting 1", context="Context 1")
    second = card(title="Titel 2", context="Context 2")

    result = service.translate_feed(feed(first, second), "en")

    assert len(translator.calls) == 1
    texts, source, target = translator.calls[0]
    assert (source, target) == ("nl", "en")
    assert texts == [
        "Titel 1", "Samenvatting 1", "Context 1",
        "Titel 2", "Context 2",
        "Beschrijving", "Beschrijving",
    ]
    assert texts_of(result) == [
        ("EN:Titel 1", "EN:Context 1", "EN:Beschrijving"),
        ("EN:Titel 2", "EN:Context 2", "EN:Beschrijving"),
    ]
    assert result.stories[0].story.summary == "EN:Samenvatting 1"
    # No summary to translate, so it stays empty.
    assert result.stories[1].story.summary is None
    assert len(stories.saved) == 2
    assert [row.source_description for row in articles.saved] == ["Beschrijving", "Beschrijving"]


def test_scores_status_and_order_are_kept(service):
    first, second = card(title="Eerste"), card(title="Tweede")
    original = Feed(FeedStatus.available, [RankedStory(first, 9.5), RankedStory(second, 1.25)])

    result = service.translate_feed(original, "en")

    assert result.status == FeedStatus.available
    assert [(r.story.id, r.score) for r in result.stories] == [(first.id, 9.5), (second.id, 1.25)]


def test_everything_cached_means_no_google_call(service, translator, stories, articles):
    story = card()
    stories.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", "Cached title", None, "Cached context", updated_at=LATER
    )
    lead = story.lead_article
    articles.translations[(lead.id, "en")] = ArticleTranslation(
        lead.id, "en", "Beschrijving", "Cached description", LATER
    )

    result = service.translate_feed(feed(story), "en")

    assert translator.calls == []
    assert texts_of(result) == [("Cached title", "Cached context", "Cached description")]


def test_a_story_changed_after_translating_is_redone(service, translator, stories):
    story = card(updated=LATER + timedelta(hours=1))
    stories.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", "Old title", None, "Old context", updated_at=LATER
    )

    result = service.translate_feed(feed(story), "en")

    assert translator.calls[0][0][:2] == ["Titel", "Context"]
    assert result.stories[0].story.title == "EN:Titel"


def test_a_changed_description_is_redone(service, translator, articles):
    story = card(lead=article(description="Nieuwe beschrijving"))
    lead = story.lead_article
    articles.translations[(lead.id, "en")] = ArticleTranslation(
        lead.id, "en", "Oude beschrijving", "Old description", LATER
    )

    result = service.translate_feed(feed(story), "en")

    assert "Nieuwe beschrijving" in translator.calls[0][0]
    assert result.stories[0].story.lead_article.description == "EN:Nieuwe beschrijving"
    assert articles.saved[-1].source_description == "Nieuwe beschrijving"


def test_a_lead_article_shared_by_two_stories_is_translated_once(service, translator):
    shared = article()

    service.translate_feed(feed(card(lead=shared), card(lead=shared)), "en")

    assert translator.calls[0][0].count("Beschrijving") == 1


def test_cards_without_lead_or_description_send_no_description(service, translator, articles):
    service.translate_feed(feed(card(lead=None), card(lead=article(description=None))), "en")

    assert "Beschrijving" not in translator.calls[0][0]
    assert articles.saved == []


def test_google_failing_keeps_cached_english_and_the_rest_dutch(
    stories, articles, caplog
):
    translator = FakeTranslator(error=TranslationUnavailableError("Translation quota exceeded"))
    service = StoryService(stories=stories, articles=articles, tags=None, translator=translator)
    cached, cold = card(title="Gecachet"), card(title="Nieuw")
    stories.translations[(cached.id, "en")] = StoryTranslation(
        cached.id, "en", "Cached", None, "Cached context", updated_at=LATER
    )

    with caplog.at_level(logging.ERROR, logger="Backend.Logic.story_service"):
        result = service.translate_feed(feed(cached, cold), "en")

    assert texts_of(result) == [
        ("Cached", "Cached context", "Beschrijving"),
        ("Nieuw", "Context", "Beschrijving"),
    ]
    assert stories.saved == [] and articles.saved == []
    assert "Translation quota exceeded" in caplog.text
    # The error log must not leak the news text itself.
    assert "Nieuw" not in caplog.text


def test_google_failing_never_shows_an_outdated_translation(stories, articles):
    translator = FakeTranslator(error=TranslationUnavailableError("offline"))
    service = StoryService(stories=stories, articles=articles, tags=None, translator=translator)
    story = card(updated=LATER + timedelta(hours=1), lead=article(description="Nieuw"))
    stories.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", "Outdated title", None, "Outdated context", updated_at=LATER
    )
    lead = story.lead_article
    articles.translations[(lead.id, "en")] = ArticleTranslation(
        lead.id, "en", "Oud", "Outdated description", LATER
    )

    result = service.translate_feed(feed(story), "en")

    assert texts_of(result) == [("Titel", "Context", "Nieuw")]


def test_no_translator_configured_falls_back_without_failing(stories, articles):
    service = StoryService(stories=stories, articles=articles, tags=None, translator=None)

    result = service.translate_feed(feed(card()), "en")

    assert texts_of(result) == [("Titel", "Context", "Beschrijving")]


def test_the_original_cards_are_not_changed(service):
    story = card()

    service.translate_feed(feed(story), "en")

    assert (story.title, story.lead_article.description) == ("Titel", "Beschrijving")
