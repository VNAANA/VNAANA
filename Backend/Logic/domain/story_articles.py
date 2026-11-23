import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Backend.Logic.domain.article import Article


@dataclass
class StoryArticleDetails:
    article: Article
    similarity_score: Decimal | None
    is_primary: bool
    added_at: datetime


@dataclass
class StoryArticlesPage:
    story_id: uuid.UUID
    articles_count: int
    limit: int
    offset: int
    articles: list[StoryArticleDetails]
