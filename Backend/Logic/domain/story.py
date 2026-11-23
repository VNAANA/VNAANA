import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from Backend.Logic.domain.story_articles import StoryArticleDetails
from Backend.Logic.domain.tag import Tag


class StoryStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


@dataclass
class Story:
    id: uuid.UUID
    title: str
    summary: str | None
    context: str | None
    status: StoryStatus
    first_published_at: datetime | None
    last_updated_at: datetime
    img_url: str | None = None
    articles_count: int = 0


@dataclass
class StoryTagDetails:
    tag: Tag
    relevance_score: Decimal | None


@dataclass
class StoryDetails(Story):
    tags: list[StoryTagDetails] = field(default_factory=list)
    articles: list[StoryArticleDetails] = field(default_factory=list)
