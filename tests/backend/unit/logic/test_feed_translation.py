"""StoryService.with_feed_translations and list_stories(language=...): lists
show the translations saved by the Translate button, never call Google, and
only use text that is still up to date. No database."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from Backend.Logic.domain.article import Article, ArticleProvider
from Backend.Logic.domain.feed import Feed, FeedStatus, RankedStory
from Backend.Logic.domain.story import StoryCard, StoryStatus
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.story_service import StoryService

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=1)


class FakeStoryRepository:
    def __init__(self):
        self.translations = {}
        self.lookups = []
        self.listed = []

    def get_translations(self, story_ids, language):
        self.lookups.append((list(story_ids), language))
        return {
            story_id: self.translations[(story_id, language)]
            for story_id in story_ids
            if (story_id, language) in self.translations
        }

    def save_translation(self, *args, **kwargs):
        raise AssertionError("Lists must not save translations")

    def list(self, **kwargs):
        return self.listed

    def to_cards(self, stories):
        return stories


class FailingTranslator:
    def translate(self, texts, *, source, target):
        raise AssertionError("Lists must not call Google")


@pytest.fixture
def stories():
    return FakeStoryRepository()


@pytest.fixture
def service(stories):
    return StoryService(stories=stories, articles=None, tags=None, translator=FailingTranslator())


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


def translate(stories, story, *, title="Title", context="Context EN", description="Description",
              updated=LATER):
    stories.translations[(story.id, "en")] = StoryTranslation(
        story.id, "en", title, None, context, updated_at=updated,
        description=description,
    )


def feed(*cards):
    return Feed(FeedStatus.available, [RankedStory(c, 1.0) for c in cards])


def texts_of(result):
    return [
        (
            r.story.title,
            r.story.context,
            r.story.lead_article and r.story.lead_article.description,
            r.story.translated_into,
        )
        for r in result.stories
    ]


@pytest.mark.parametrize("language", [None, "nl", "NL", "de"])
def test_original_language_is_returned_untouched(service, stories, language):
    original = feed(card())

    assert service.with_feed_translations(original, language) is original
    assert stories.lookups == []


def test_a_feed_without_stories_looks_nothing_up(service, stories):
    locked = Feed(FeedStatus.locked)

    assert service.with_feed_translations(locked, "en") is locked
    assert stories.lookups == []


def test_translated_stories_are_shown_translated_and_the_rest_dutch(service, stories):
    translated, untouched = card(), card(title="Nieuw")
    translate(stories, translated)

    result = service.with_feed_translations(feed(translated, untouched), "en")

    assert texts_of(result) == [
        ("Title", "Context EN", "Description", "en"),
        ("Nieuw", "Context", "Beschrijving", None),
    ]
    # One lookup for the whole page.
    assert stories.lookups == [([translated.id, untouched.id], "en")]


def test_scores_status_and_order_are_kept(service):
    first, second = card(title="Eerste"), card(title="Tweede")
    original = Feed(FeedStatus.available, [RankedStory(first, 9.5), RankedStory(second, 1.25)])

    result = service.with_feed_translations(original, "en")

    assert result.status == FeedStatus.available
    assert [(r.story.id, r.score) for r in result.stories] == [(first.id, 9.5), (second.id, 1.25)]


def test_a_story_changed_after_translating_is_shown_in_dutch(service, stories):
    story = card(updated=LATER + timedelta(hours=1))
    translate(stories, story)

    result = service.with_feed_translations(feed(story), "en")

    # An outdated translation is never shown, the description included.
    assert texts_of(result) == [("Titel", "Context", "Beschrijving", None)]


def test_a_translation_without_description_shows_it_in_dutch(service, stories):
    story = card()
    translate(stories, story, description=None)

    result = service.with_feed_translations(feed(story), "en")

    assert texts_of(result) == [("Title", "Context EN", "Beschrijving", None)]


def test_a_new_lead_article_without_description_counts_as_translated(service, stories):
    story = card(lead=article(description=None))
    translate(stories, story)

    result = service.with_feed_translations(feed(story), "en")

    assert texts_of(result) == [("Title", "Context EN", None, "en")]


def test_a_summary_added_after_translating_stays_dutch(service, stories):
    story = card(summary="Samenvatting")
    translate(stories, story)

    result = service.with_feed_translations(feed(story), "en")

    assert result.stories[0].story.summary == "Samenvatting"
    assert result.stories[0].story.translated_into is None


def test_the_original_cards_are_not_changed(service, stories):
    story = card()
    translate(stories, story)

    service.with_feed_translations(feed(story), "en")

    assert (story.title, story.lead_article.description) == ("Titel", "Beschrijving")


def test_list_stories_shows_saved_translations(service, stories):
    translated, untouched = card(), card(title="Nieuw")
    translate(stories, translated)
    stories.listed = [translated, untouched]

    result = service.list_stories(language="en")

    assert [story.title for story in result] == ["Title", "Nieuw"]


def test_list_stories_signed_out_looks_nothing_up(service, stories):
    stories.listed = [card()]

    assert service.list_stories()[0].title == "Titel"
    assert stories.lookups == []
