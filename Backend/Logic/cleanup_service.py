"""Removes stories and articles that are too old to show."""

from datetime import datetime, timedelta, timezone

from Backend.Logic.Algorithm.decay import LIFETIME_DAYS
from Backend.Logic.ports.article_repository import ArticleRepository
from Backend.Logic.ports.story_repository import StoryRepository


class CleanupService:
    def __init__(
        self,
        story_repository: StoryRepository,
        article_repository: ArticleRepository,
    ) -> None:
        self.story_repository = story_repository
        self.article_repository = article_repository

    def delete_expired(self, now: datetime | None = None) -> dict[str, int]:
        """
        Delete stories not updated and articles not seen in a feed for
        LIFETIME_DAYS. By then a story's decay has reached 0, so it would
        never be ranked in a feed again anyway.

        The caller owns the transaction and commit.

        Returns how many stories and articles were deleted.
        """
        now = now or datetime.now(timezone.utc)
        cutoff = now - timedelta(days=LIFETIME_DAYS)

        # Stories go first. Deleting a story also deletes its article links,
        # so its old articles can be removed in the next step.
        stories_deleted = self.story_repository.delete_older_than(cutoff)

        # An old article that is still linked to a remaining (fresh) story is
        # kept, so a story never loses its sources while it is still shown.
        articles_deleted = self.article_repository.delete_unlinked_older_than(
            cutoff
        )

        return {
            "stories": stories_deleted,
            "articles": articles_deleted,
        }
