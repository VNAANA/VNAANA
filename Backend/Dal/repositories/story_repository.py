from __future__ import annotations

import uuid
from dataclasses import asdict
from dataclasses import fields as dataclass_fields
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session, selectinload

from Backend.Dal.models import (
    Story as StoryModel,
)
from Backend.Dal.models import (
    StoryArticle as StoryArticleModel,
)
from Backend.Dal.models import (
    StoryStatus,
)
from Backend.Dal.models import (
    StoryTag as StoryTagModel,
)
from Backend.Dal.models import (
    StoryTranslation as StoryTranslationModel,
)
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Logic.domain.story import Story, StoryCard, StoryDetails, StoryTagDetails
from Backend.Logic.domain.story_article_link import StoryArticleLink
from Backend.Logic.domain.story_articles import StoryArticleDetails, StoryArticlesPage
from Backend.Logic.domain.story_translation import StoryTranslation
from Backend.Logic.domain.tag import Tag
from Backend.Logic.ports.story_repository import (
    GenreTagWrite,
)
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
            img_url=story.img_url,
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
        return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    # ---- stories ----

    def get(self, story_id: uuid.UUID) -> StoryDetails | None:
        story = self.db.scalar(
            select(StoryModel)
            .where(StoryModel.id == story_id)
            .execution_options(populate_existing=True)
            .options(
                selectinload(StoryModel.tags),
                selectinload(StoryModel.articles).selectinload(
                    StoryArticleModel.article
                ),
            )
        )

        if story is None:
            return None

        result = StoryDetails(**asdict(self._to_domain(story)))
        result.tags = [
            StoryTagDetails(Tag(link.tag.id, link.tag.name), link.relevance_score)
            for link in sorted(story.tags, key=lambda link: str(link.tag_id))
        ]
        result.articles = [
            StoryArticleDetails(
                ArticleRepository._to_domain(link.article),
                link.similarity_score,
                link.is_primary,
                link.added_at,
            )
            for link in sorted(
                story.articles,
                key=lambda link: (
                    not link.is_primary,
                    link.added_at,
                    str(link.article_id),
                ),
            )
        ]
        result.articles_count = len(result.articles)
        return result

    def list(
        self,
        *,
        status: StoryStatus | None = None,
        tag_ids: list[uuid.UUID] | None = None,
        search_terms: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Story]:
        count = (
            select(func.count())
            .select_from(StoryArticleModel)
            .where(StoryArticleModel.story_id == StoryModel.id)
            .correlate(StoryModel)
            .scalar_subquery()
        )
        stmt = select(StoryModel, count.label("articles_count"))

        if status is not None:
            stmt = stmt.where(StoryModel.status == status)

        if tag_ids:
            # Stories with any of the tags. A subquery instead of a join, so a
            # story with several of them is still listed once.
            tagged = select(StoryTagModel.story_id).where(
                StoryTagModel.tag_id.in_(tag_ids)
            )
            stmt = stmt.where(StoryModel.id.in_(tagged))

        # Search looks at the title only: every word must appear in it. Combined
        # with tag_ids above, it searches only the stories with those tags.
        for term in search_terms or []:
            pattern = f"%{self._escape_like(term)}%"
            stmt = stmt.where(StoryModel.title.ilike(pattern, escape="\\"))

        stmt = (
            stmt.order_by(StoryModel.last_updated_at.desc(), StoryModel.id)
            .limit(limit)
            .offset(offset)
        )

        results = []
        for story, articles_count in self.db.execute(stmt):
            item = self._to_domain(story)
            item.articles_count = articles_count
            results.append(item)
        return results

    def to_cards(self, stories: list[Story]) -> list[StoryCard]:
        if not stories:
            return []
        story_ids = [story.id for story in stories]

        tags: dict[uuid.UUID, list[StoryTagDetails]] = {
            story_id: [] for story_id in story_ids
        }
        tag_links = self.db.scalars(
            select(StoryTagModel).where(StoryTagModel.story_id.in_(story_ids))
        ).unique()
        for link in tag_links:
            tags[link.story_id].append(
                StoryTagDetails(Tag(link.tag.id, link.tag.name), link.relevance_score)
            )
        for story_tags in tags.values():
            # Most relevant first; tags without a score last, then by name for a stable order.
            story_tags.sort(
                key=lambda item: (
                    item.relevance_score is None,
                    -(item.relevance_score or 0),
                    item.tag.name,
                )
            )

        counts = dict(
            self.db.execute(
                select(StoryArticleModel.story_id, func.count())
                .where(StoryArticleModel.story_id.in_(story_ids))
                .group_by(StoryArticleModel.story_id)
            ).all()
        )

        # The lead article per story: the primary one, else the first linked
        # (the same order GET /stories/{id}/articles uses).
        rank = (
            func.row_number()
            .over(
                partition_by=StoryArticleModel.story_id,
                order_by=(
                    StoryArticleModel.is_primary.desc(),
                    StoryArticleModel.added_at,
                    StoryArticleModel.article_id,
                ),
            )
            .label("rank")
        )
        ranked = (
            select(StoryArticleModel.story_id, StoryArticleModel.article_id, rank)
            .where(StoryArticleModel.story_id.in_(story_ids))
            .subquery()
        )
        lead_links = self.db.scalars(
            select(StoryArticleModel)
            .join(
                ranked,
                (StoryArticleModel.story_id == ranked.c.story_id)
                & (StoryArticleModel.article_id == ranked.c.article_id),
            )
            .where(ranked.c.rank == 1)
        ).unique()
        leads = {
            link.story_id: ArticleRepository._to_domain(link.article)
            for link in lead_links
        }

        return [
            StoryCard(
                # Only the base Story fields, so a StoryDetails passed in works too.
                **{
                    **{
                        name.name: getattr(story, name.name)
                        for name in dataclass_fields(Story)
                    },
                    "articles_count": counts.get(story.id, 0),
                },
                tags=tags[story.id],
                lead_article=leads.get(story.id),
            )
            for story in stories
        ]

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

    def _lock_story_for_tags(
        self,
        story_id: uuid.UUID,
    ) -> Row[tuple[uuid.UUID, str, str | None, str | None]] | None:
        return self.db.execute(
            select(
                StoryModel.id, StoryModel.title, StoryModel.summary, StoryModel.context
            )
            .where(StoryModel.id == story_id)
            .with_for_update()
        ).one_or_none()

    def add_genre_tags_if_current(
        self,
        snapshot: Story,
        tags: dict[uuid.UUID, Decimal | None],
    ) -> GenreTagWrite:
        story = self._lock_story_for_tags(snapshot.id)
        if story is None:
            return "missing"
        if (story.title, story.summary, story.context) != (
            snapshot.title,
            snapshot.summary,
            snapshot.context,
        ):
            return "changed"
        if (
            self.db.scalar(
                select(StoryTagModel.tag_id)
                .where(StoryTagModel.story_id == story.id)
                .limit(1)
            )
            is not None
        ):
            return "already_tagged"

        self.db.add_all(
            StoryTagModel(story_id=story.id, tag_id=tag_id, relevance_score=score)
            for tag_id, score in tags.items()
        )
        self.db.flush()
        return "saved"

    def replace_tags(
        self,
        story: Story,
        tags: dict[uuid.UUID, Decimal | None],
    ) -> None:
        # Serialize manual replacement with automatic insertion on PostgreSQL.
        self._lock_story_for_tags(story.id)
        stmt = select(StoryTagModel).where(StoryTagModel.story_id == story.id)

        current_links = list(self.db.scalars(stmt))
        current = {link.tag_id: link for link in current_links}

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

    def list_articles(
        self, story_id: uuid.UUID, *, limit: int, offset: int
    ) -> StoryArticlesPage:
        predicate = StoryArticleModel.story_id == story_id
        count = self.db.scalar(
            select(func.count()).select_from(StoryArticleModel).where(predicate)
        )
        links = self.db.scalars(
            select(StoryArticleModel)
            .where(predicate)
            .options(selectinload(StoryArticleModel.article))
            .order_by(
                StoryArticleModel.is_primary.desc(),
                StoryArticleModel.added_at,
                StoryArticleModel.article_id,
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return StoryArticlesPage(
            story_id,
            count,
            limit,
            offset,
            [
                StoryArticleDetails(
                    ArticleRepository._to_domain(link.article),
                    link.similarity_score,
                    link.is_primary,
                    link.added_at,
                )
                for link in links
            ],
        )

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

    # ---- story_translations ----

    @staticmethod
    def _translation_to_domain(row: StoryTranslationModel) -> StoryTranslation:
        return StoryTranslation(
            story_id=row.story_id,
            language=row.language,
            title=row.title,
            summary=row.summary,
            context=row.context,
            updated_at=row.updated_at,
            description=row.description,
        )

    def get_translation(
        self,
        story_id: uuid.UUID,
        language: str,
    ) -> StoryTranslation | None:
        row = self.db.get(StoryTranslationModel, (story_id, language))

        if row is None:
            return None

        return self._translation_to_domain(row)

    def get_translations(
        self,
        story_ids: list[uuid.UUID],
        language: str,
    ) -> dict[uuid.UUID, StoryTranslation]:
        if not story_ids:
            return {}

        rows = self.db.scalars(
            select(StoryTranslationModel).where(
                StoryTranslationModel.story_id.in_(story_ids),
                StoryTranslationModel.language == language,
            )
        )

        return {row.story_id: self._translation_to_domain(row) for row in rows}

    def save_translation(
        self,
        story_id: uuid.UUID,
        language: str,
        *,
        title: str | None,
        summary: str | None,
        context: str | None,
        description: str | None = None,
    ) -> StoryTranslation:
        fields = {
            "title": title,
            "summary": summary,
            "context": context,
            "description": description,
        }

        # Upsert: two users translating the same story at the same
        # time would otherwise both insert and the second one would hit the
        # primary key. onupdate doesn't run for ON CONFLICT, so updated_at is
        # set here explicitly.
        stmt = insert(StoryTranslationModel).values(
            story_id=story_id,
            language=language,
            **fields,
            updated_at=func.now(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                StoryTranslationModel.story_id,
                StoryTranslationModel.language,
            ],
            set_={**fields, "updated_at": func.now()},
        ).returning(StoryTranslationModel)

        row = self.db.scalars(
            stmt,
            execution_options={"populate_existing": True},
        ).one()

        return self._translation_to_domain(row)
