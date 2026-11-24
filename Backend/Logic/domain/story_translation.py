import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class StoryTranslation:
    """A story's text in one other language, saved so it is only translated once.

    A field is None when the original story had no text for it at the time
    of translating (summary is often still empty).

    description is the story's lead article description. Like the story's
    own fields, it counts as outdated once the story changed after
    updated_at.
    """

    story_id: uuid.UUID
    language: str
    title: str | None
    summary: str | None
    context: str | None
    updated_at: datetime
    description: str | None = None
