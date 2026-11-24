import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ArticleTranslation:
    """An article's description in one other language, cached so it is only
    translated once.

    source_description is the original text that was translated. Articles get
    their description refreshed on every ingest without last_updated_at always
    changing, so comparing the text is the only reliable way to tell whether
    the translation is still up to date.
    """

    article_id: uuid.UUID
    language: str
    source_description: str
    description: str
    updated_at: datetime
