import uuid
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from Backend.Logic.domain.story import Story, StoryStatus
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
TRANSLATED_FIELDS = ("title", "summary", "context")


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
        tag_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Story]:
        return self.stories.list(
            status=status,
            tag_id=tag_id,
            search_terms=self._search_terms(q),
            limit=limit,
            offset=offset,
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

    def get_story_in_language(
        self,
        story_id: uuid.UUID,
        language: str | None,
    ) -> Story:
        """Return the story with its text in the given language.

        No language, Dutch, or a language we don't translate to returns the
        original story. Otherwise the cached translation is used, and Google
        is only called for text that has no up-to-date translation yet.
        """
        story = self.get_story(story_id)
        target = (language or SOURCE_LANGUAGE).strip().lower()

        if target == SOURCE_LANGUAGE or target not in TRANSLATION_TARGETS:
            return story

        cached = self.stories.get_translation(story_id, target)
        # The story changed after it was translated, so every field is redone.
        stale = cached is not None and cached.updated_at < story.last_updated_at

        missing = {
            name: getattr(story, name)
            for name in TRANSLATED_FIELDS
            if getattr(story, name)
            and (cached is None or stale or getattr(cached, name) is None)
        }

        if missing:
            cached = self._translate_and_save(story, target, cached, missing)

        if cached is None:
            # The story has no text at all, so there was nothing to translate.
            return story

        return replace(story, **{
            # A field the story has no text for stays empty, even if an
            # older translation still holds text for it.
            name: getattr(cached, name) if getattr(story, name) else getattr(story, name)
            for name in TRANSLATED_FIELDS
        })

    def _translate_and_save(
        self,
        story: Story,
        target: str,
        cached: StoryTranslation | None,
        missing: dict[str, str],
    ) -> StoryTranslation:
        if self.translator is None:
            raise TranslationUnavailableError("Translation is not configured")

        translated = dict(zip(
            missing,
            self.translator.translate(
                list(missing.values()),
                source=SOURCE_LANGUAGE,
                target=target,
            ),
        ))

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
                fields[name] = getattr(cached, name)

        return self.stories.save_translation(story.id, target, **fields)

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
        self, snapshot: Story, tags: dict[uuid.UUID, float | None],
    ) -> GenreTagWrite:
        if not tags:
            raise ValueError("Genre tags must not be empty")
        return self.stories.add_genre_tags_if_current(snapshot, self._tag_scores(tags))

    def _tag_scores(
        self, tags: dict[uuid.UUID, float | None],
    ) -> dict[uuid.UUID, Decimal | None]:
        found = {
            tag.id
            for tag in self.tags.get_many(list(tags))
        }

        missing = [
            tag_id
            for tag_id in tags
            if tag_id not in found
        ]

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

        if self.stories.get_article_link(
            story_id,
            article_id,
        ) is not None:
            raise ConflictError(
                "Article is already linked to this story"
            )

        if is_primary:
            self.stories.clear_primary(story_id)

        link = self.stories.add_article_link(
            story_id=story_id,
            article_id=article_id,
            similarity_score=(
                Decimal(str(similarity_score))
                if similarity_score is not None
                else None
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
