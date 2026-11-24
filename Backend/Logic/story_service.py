import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from Backend.Logic.domain.feed import Feed, RankedStory
from Backend.Logic.domain.story import Story, StoryCard, StoryStatus
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.exceptions import (
    ConflictError,
    InvalidSearchError,
    NotFoundError,
    TranslationUnavailableError,
)
from Backend.Logic.ports.article_repository import ArticleRepository
from Backend.Logic.ports.story_repository import GenreTagWrite, StoryRepository
from Backend.Logic.ports.tag_repository import TagRepository
from Backend.Logic.ports.translator import Translator

MIN_SEARCH_LENGTH = 2

# All collected news is Dutch, so stories are stored in Dutch.
SOURCE_LANGUAGE = "nl"
# Languages a story can be translated into. The frontend only offers en and nl.
TRANSLATION_TARGETS = frozenset({"en"})
# Story fields that get translated. The lead article's description is
# translated too and saved with them, as "description".
TRANSLATED_FIELDS = ("title", "summary", "context")


def _is_current(saved: StoryTranslation | None, story: Story, name: str) -> bool:
    """Whether the saved translation has up-to-date text for this field.
    A story that changed after translating counts as outdated everywhere."""
    return (
        saved is not None
        and saved.updated_at >= story.last_updated_at
        and getattr(saved, name) is not None
    )


class StoryService:
    def list_articles(self, story_id: uuid.UUID, *, limit: int = 20, offset: int = 0):
        self.get_story(story_id)
        return self.stories.list_articles(story_id, limit=limit, offset=offset)

    def __init__(
        self,
        stories: StoryRepository,
        articles: ArticleRepository,
        tags: TagRepository,
        translator: Translator | None = None,
    ):
        self.stories = stories
        self.articles = articles
        self.tags = tags
        self.translator = translator

    def list_stories(
        self,
        *,
        status: StoryStatus | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
        language: str | None = None,
    ) -> list[StoryCard]:
        """language: show saved translations into it (the user's profile language)."""
        cards = self.stories.to_cards(
            self.stories.list(
                status=status,
                tag_ids=tag_ids,
                search_terms=self._search_terms(q),
                limit=limit,
                offset=offset,
            )
        )
        return self.with_translations(cards, language)

    def with_cards(self, feed: Feed) -> Feed:
        """The feed with its stories as cards (tags, lead article, article count)."""
        cards = self.stories.to_cards([ranked.story for ranked in feed.stories])
        return Feed(
            feed.status,
            [
                RankedStory(card, ranked.score)
                for card, ranked in zip(cards, feed.stories)
            ],
        )

    @staticmethod
    def _search_terms(q: str | None) -> list[str] | None:
        """Turns the raw search text into the words a story must all contain.

        None means "don't search": a cleared search bar still sends q="",
        and that should list stories, not fail.
        """
        if q is None:
            return None

        text = q.strip()

        if not text:
            return None

        if len(text) < MIN_SEARCH_LENGTH:
            raise InvalidSearchError(
                f"Search must be at least {MIN_SEARCH_LENGTH} characters"
            )

        # split() without an argument also handles double spaces and tabs.
        # dict.fromkeys drops repeated words but keeps their order.
        return list(dict.fromkeys(text.split()))

    def get_story(
        self,
        story_id: uuid.UUID,
    ) -> Story:
        story = self.stories.get(story_id)

        if story is None:
            raise NotFoundError("Story", story_id)

        return story

    # ---- translation ----
    #
    # Google is only called when the user presses Translate on a post
    # (translate_story). Everywhere else a story is shown with the
    # translation that is already saved, as far as it is still up to date,
    # and the rest stays Dutch.

    def get_story_in_language(
        self,
        story_id: uuid.UUID,
        language: str | None,
    ) -> Story:
        """The story with its saved translation for this language, if any.
        Never calls Google."""
        story = self.get_story(story_id)
        target = self._translation_target(language)

        if target is None:
            return story

        return self._with_translation(
            story, self.stories.get_translation(story_id, target), target
        )

    def with_translations(
        self,
        stories: list[Story],
        language: str | None,
    ) -> list[Story]:
        """The stories with their saved translations for this language.
        One query for all of them; never calls Google."""
        target = self._translation_target(language)

        if target is None or not stories:
            return stories

        saved = self.stories.get_translations([story.id for story in stories], target)

        return [
            self._with_translation(story, saved.get(story.id), target)
            for story in stories
        ]

    def with_feed_translations(self, feed: Feed, language: str | None) -> Feed:
        """The feed's cards with their saved translations; scores and order stay."""
        if self._translation_target(language) is None or not feed.stories:
            return feed

        cards = self.with_translations(
            [ranked.story for ranked in feed.stories], language
        )

        return Feed(
            feed.status,
            [RankedStory(card, ranked.score) for card, ranked in zip(cards, feed.stories)],
        )

    def translate_story(
        self,
        story_id: uuid.UUID,
        language: str | None,
    ) -> StoryCard:
        """Translate the post into this language and save it: the story's
        title, summary and context, and the lead article's description.

        Only text without an up-to-date translation goes to Google, all of it
        in one request. No language, Dutch, or a language we don't translate
        to returns the original card. A failed translation saves nothing and
        raises TranslationUnavailableError.
        """
        card = self.stories.to_cards([self.get_story(story_id)])[0]
        target = self._translation_target(language)

        if target is None:
            return card

        saved = self.stories.get_translation(story_id, target)
        missing = self._missing_text(card, saved)

        if missing:
            translated = dict(
                zip(
                    missing,
                    self._require_translator().translate(
                        list(missing.values()),
                        source=SOURCE_LANGUAGE,
                        target=target,
                    ),
                )
            )
            saved = self._save_translation(card, target, saved, translated)

        return self._with_translation(card, saved, target)

    @staticmethod
    def _translation_target(language: str | None) -> str | None:
        """The language to translate into, or None when the original is wanted."""
        target = (language or SOURCE_LANGUAGE).strip().lower()

        if target == SOURCE_LANGUAGE or target not in TRANSLATION_TARGETS:
            return None

        return target

    @staticmethod
    def _lead_description(story: Story) -> str | None:
        if isinstance(story, StoryCard) and story.lead_article is not None:
            return story.lead_article.description or None
        return None

    @classmethod
    def _missing_text(
        cls,
        story: Story,
        saved: StoryTranslation | None,
    ) -> dict[str, str]:
        """The post's text that has no up-to-date translation yet, by field.
        "description" is the lead article's description."""
        missing = {
            name: getattr(story, name)
            for name in TRANSLATED_FIELDS
            if getattr(story, name) and not _is_current(saved, story, name)
        }

        description = cls._lead_description(story)
        if description and not _is_current(saved, story, "description"):
            missing["description"] = description

        return missing

    def _require_translator(self) -> Translator:
        if self.translator is None:
            raise TranslationUnavailableError("Translation is not configured")

        return self.translator

    def _save_translation(
        self,
        story: Story,
        target: str,
        saved: StoryTranslation | None,
        translated: dict[str, str],
    ) -> StoryTranslation:
        fields = {}
        for name in TRANSLATED_FIELDS:
            original = getattr(story, name)
            if name in translated:
                fields[name] = translated[name]
            elif not original:
                # Nothing to translate: keep None or "" as it is in the story.
                fields[name] = original
            else:
                # Still up to date from the earlier translation.
                fields[name] = getattr(saved, name)

        if "description" in translated:
            fields["description"] = translated["description"]
        elif self._lead_description(story):
            # Still up to date from the earlier translation.
            fields["description"] = saved.description
        else:
            fields["description"] = None

        return self.stories.save_translation(story.id, target, **fields)

    @classmethod
    def _with_translation(
        cls,
        story: Story,
        saved: StoryTranslation | None,
        target: str,
    ) -> Story:
        """The story with every up-to-date translated text filled in.

        Text without an up-to-date translation stays Dutch. translated_into
        is only set when nothing is left in Dutch, so the frontend knows
        whether to offer Translate.
        """
        if saved is None:
            return story

        changes = {}
        complete = True

        for name in TRANSLATED_FIELDS:
            # A field the story has no text for stays empty, even if an
            # older translation still holds text for it.
            if not getattr(story, name):
                continue
            if _is_current(saved, story, name):
                changes[name] = getattr(saved, name)
            else:
                complete = False

        if cls._lead_description(story):
            if _is_current(saved, story, "description"):
                changes["lead_article"] = replace(
                    story.lead_article, description=saved.description
                )
            else:
                complete = False

        if complete:
            changes["translated_into"] = target

        return replace(story, **changes)

    def create_story(
        self,
        data: dict[str, Any],
    ) -> Story:
        if data.get("status") == StoryStatus.published:
            data["first_published_at"] = datetime.now(timezone.utc)

        story = self.stories.add(**data)

        return self.get_story(story.id)

    def update_story(
        self,
        story_id: uuid.UUID,
        changes: dict[str, Any],
    ) -> Story:
        story = self.get_story(story_id)

        if (
            changes.get("status") == StoryStatus.published
            and story.first_published_at is None
        ):
            changes["first_published_at"] = datetime.now(timezone.utc)

        self.stories.update(
            story,
            **changes,
            last_updated_at=datetime.now(timezone.utc),
        )

        return self.get_story(story_id)

    def set_tags(
        self,
        story_id: uuid.UUID,
        tags: dict[uuid.UUID, float | None],
    ) -> Story:
        story = self.get_story(story_id)

        self.stories.replace_tags(story, self._tag_scores(tags))
        return self.get_story(story_id)

    def add_genre_tags_if_current(
        self,
        snapshot: Story,
        tags: dict[uuid.UUID, float | None],
    ) -> GenreTagWrite:
        if not tags:
            raise ValueError("Genre tags must not be empty")
        return self.stories.add_genre_tags_if_current(snapshot, self._tag_scores(tags))

    def _tag_scores(
        self,
        tags: dict[uuid.UUID, float | None],
    ) -> dict[uuid.UUID, Decimal | None]:
        found = {tag.id for tag in self.tags.get_many(list(tags))}

        missing = [tag_id for tag_id in tags if tag_id not in found]

        if missing:
            raise NotFoundError(
                "Tag",
                ", ".join(map(str, missing)),
            )

        return {
            tag_id: Decimal(str(score)) if score is not None else None
            for tag_id, score in tags.items()
        }

    def link_article(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
        similarity_score: float | None,
        is_primary: bool,
    ):
        story = self.get_story(story_id)

        if self.articles.get(article_id) is None:
            raise NotFoundError("Article", article_id)

        if (
            self.stories.get_article_link(
                story_id,
                article_id,
            )
            is not None
        ):
            raise ConflictError("Article is already linked to this story")

        if is_primary:
            self.stories.clear_primary(story_id)

        link = self.stories.add_article_link(
            story_id=story_id,
            article_id=article_id,
            similarity_score=(
                Decimal(str(similarity_score)) if similarity_score is not None else None
            ),
            is_primary=is_primary,
        )

        self.stories.update(
            story,
            last_updated_at=datetime.now(timezone.utc),
        )

        return link

    def unlink_article(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> None:
        link = self.stories.get_article_link(
            story_id,
            article_id,
        )

        if link is None:
            raise NotFoundError(
                "Story article link",
                f"{story_id}/{article_id}",
            )

        self.stories.remove_article_link(
            story_id,
            article_id,
        )
