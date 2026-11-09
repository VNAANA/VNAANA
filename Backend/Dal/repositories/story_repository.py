import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, or_, select, update
from sqlalchemy.orm import Session, selectinload

from Backend.Dal.models import (
    Story as StoryModel,
    StoryArticle as StoryArticleModel,
    StoryStatus,
    StoryTag as StoryTagModel,
)
from Backend.Logic.domain.story import Story
from Backend.Logic.domain.story_article_link import StoryArticleLink
from Backend.Logic.ports.story_repository import (
    StoryRepository as StoryRepositoryPort,
)


class StoryRepository(StoryRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    # ---- mappings ----

    @staticmethod
    def _to_domain(story: StoryModel) -> Story:
        return Story(
            id=story.id,
            title=story.title,
            summary=story.summary,
            context=story.context,
            status=story.status,
            first_published_at=story.first_published_at,
            last_updated_at=story.last_updated_at,
        )

    @staticmethod
    def _article_link_to_domain(
        link: StoryArticleModel,
    ) -> StoryArticleLink:
        return StoryArticleLink(
            story_id=link.story_id,
            article_id=link.article_id,
            similarity_score=link.similarity_score,
            is_primary=link.is_primary,
            added_at=link.added_at,
        )

    @staticmethod
    def _escape_like(term: str) -> str:
        # % and _ are wildcards in LIKE; without this a search for "100%"
        # would match "100" followed by anything. The backslash goes first,
        # otherwise the backslashes added below would get escaped again.
        return (
            term
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

    # ---- stories ----

    def get(self, story_id: uuid.UUID) -> Story | None:
        story = self.db.get(StoryModel, story_id)

        if story is None:
            return None

        return self._to_domain(story)

    def list(
        self,
        *,
        status: StoryStatus | None = None,
        tag_id: uuid.UUID | None = None,
        search_terms: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Story]:
        stmt = select(StoryModel)

        if status is not None:
            stmt = stmt.where(StoryModel.status == status)

        if tag_id is not None:
            stmt = (
                stmt
                .join(StoryTagModel)
                .where(StoryTagModel.tag_id == tag_id)
            )

        for term in search_terms or []:
            pattern = f"%{self._escape_like(term)}%"
            stmt = stmt.where(
                or_(
                    StoryModel.title.ilike(pattern, escape="\\"),
                    StoryModel.summary.ilike(pattern, escape="\\"),
                )
            )

        stmt = (
            stmt
            .order_by(StoryModel.last_updated_at.desc())
            .limit(limit)
            .offset(offset)
        )

        stories = self.db.scalars(stmt)

        return [self._to_domain(story) for story in stories]

    def add(self, **fields: Any) -> Story:
        story_model = StoryModel(**fields)

        self.db.add(story_model)
        self.db.flush()

        return self._to_domain(story_model)

    def update(self, story: Story, **fields: Any) -> Story:
        story_model = self.db.get(StoryModel, story.id)

        if story_model is None:
            raise ValueError(f"Story {story.id} not found")

        for key, value in fields.items():
            setattr(story_model, key, value)

        self.db.flush()

        return self._to_domain(story_model)

    # ---- story_tags ----

    def replace_tags(
        self,
        story: Story,
        tags: dict[uuid.UUID, Decimal | None],
    ) -> None:
        stmt = select(StoryTagModel).where(
            StoryTagModel.story_id == story.id
        )

        current_links = list(self.db.scalars(stmt))
        current = {
            link.tag_id: link
            for link in current_links
        }

        for tag_id, link in current.items():
            if tag_id not in tags:
                self.db.delete(link)

        for tag_id, score in tags.items():
            if tag_id in current:
                current[tag_id].relevance_score = score
            else:
                self.db.add(
                    StoryTagModel(
                        story_id=story.id,
                        tag_id=tag_id,
                        relevance_score=score,
                    )
                )

        self.db.flush()

    # ---- story_articles ----

    def get_article_link(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> StoryArticleLink | None:
        link = self.db.get(
            StoryArticleModel,
            (story_id, article_id),
        )

        if link is None:
            return None

        return self._article_link_to_domain(link)

    def add_article_link(
        self,
        *,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
        similarity_score: Decimal | None = None,
        is_primary: bool = False,
    ) -> StoryArticleLink:
        link_model = StoryArticleModel(
            story_id=story_id,
            article_id=article_id,
            similarity_score=similarity_score,
            is_primary=is_primary,
        )

        self.db.add(link_model)
        self.db.flush()

        return self._article_link_to_domain(link_model)

    def clear_primary(self, story_id: uuid.UUID) -> None:
        self.db.execute(
            update(StoryArticleModel)
            .where(
                StoryArticleModel.story_id == story_id,
                StoryArticleModel.is_primary.is_(True),
            )
            .values(is_primary=False)
        )

        self.db.flush()

    def remove_article_link(
        self,
        story_id: uuid.UUID,
        article_id: uuid.UUID,
    ) -> None:
        link = self.db.get(
            StoryArticleModel,
            (story_id, article_id),
        )

        if link is None:
            return

        self.db.delete(link)
        self.db.flush()

    # ---- cleanup ----

    def delete_older_than(self, cutoff: datetime) -> int:
        # The database removes the story's tags, article links and reactions
        # through ON DELETE CASCADE. Engagement events keep their row, with
        # story_id set to NULL.
        result = self.db.execute(
            delete(StoryModel)
            .where(StoryModel.last_updated_at < cutoff)
            .execution_options(synchronize_session=False)
        )

        return result.rowcount
