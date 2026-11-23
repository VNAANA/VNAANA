import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoryTranslation:
    """A story's text in one other language, cached so it is only translated once.

    A field is None when the original story had no text for it at the time
    of translating (summary is often still empty).
    """

    story_id: uuid.UUID
    language: str
    title: str | None
    summary: str | None
    context: str | None
    updated_at: datetime
