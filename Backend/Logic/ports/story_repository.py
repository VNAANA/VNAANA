from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from Backend.Logic.domain.story import Story, StoryCard, StoryStatus
from Backend.Logic.domain.story_article_link import StoryArticleLink
from Backend.Logic.domain.story_articles import StoryArticlesPage
from Backend.Logic.domain.story_translation import StoryTranslation

GenreTagWrite = Literal["saved", "missing", "changed", "already_tagged"]


class StoryRepository(Protocol):
    def list_articles(
        self, story_id: uuid.UUID, *, limit: int, offset: int
    ) -> StoryArticlesPage: ...

    def get(self, story_id: uuid.UUID) -> Story | None: ...

    def list(
        self,
        *,
        status: StoryStatus | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        search_terms: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Story]:
        """tag_ids: stories with at least one of these tags.
        search_terms: every word must appear in the title or the summary."""
        ...

    def to_cards(self, stories: list[Story]) -> list[StoryCard]:
        """The same stories, in the same order, with tags, lead article and
        article count. Loads them for all stories at once."""
        ...

    def add(self, **fields: Any) -> Story: ...

    def update(self, story: Story, **fields: Any) -> Story: ...

    def replace_tags(
        self,
        story: Story,
        tags: dict[uuid.UUID, Decimal | None],
    ) -> None: ...

    def add_genre_tags_if_current(
        self,
        snapshot: Story,
        tags: dict[uuid.UUID, Decimal | None],
    ) -> GenreTagWrite: ...

    def get_article_link(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> StoryArticleLink | None: ...

    def add_article_link(
        self,
        *,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
        similarity_score: Decimal | None = None,
        is_primary: bool = False,
    ) -> StoryArticleLink: ...

    def clear_primary(self, story_id: uuid.UUID) -> None: ...

    def remove_article_link(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> None: ...

    def delete_older_than(self, cutoff: datetime) -> int:
        """Delete every story last updated before cutoff. Returns how many."""
        ...

    def get_translation(
        self,
        story_id: uuid.UUID,
        language: str,
    ) -> StoryTranslation | None: ...

    def save_translation(
        self,
        story_id: uuid.UUID,
        language: str,
        *,
        title: str | None,
        summary: str | None,
        context: str | None,
    ) -> StoryTranslation:
        """Insert or overwrite the translation for this story and language."""
        ...
