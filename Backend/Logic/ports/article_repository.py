import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List

from Backend.Logic.domain.article import Article
from Backend.Logic.domain.article_translation import ArticleTranslation

ArticleList = List[Article]


class ArticleRepository(ABC):
    @abstractmethod
    def get(
        self,
        article_id: uuid.UUID,
    ) -> Article | None: ...

    @abstractmethod
    def get_by_canonical_url(
        self,
        canonical_url: str,
    ) -> Article | None: ...

    @abstractmethod
    def list(
        self,
        *,
        provider_id: uuid.UUID | None = None,
        language: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Article]: ...

    @abstractmethod
    def list_random(
        self,
        *,
        limit: int = 5,
    ) -> ArticleList: ...

    @abstractmethod
    def list_unscraped(
        self,
        *,
        limit: int = 100,
    ) -> ArticleList: ...

    @abstractmethod
    def add(
        self,
        **fields: Any,
    ) -> Article: ...

    @abstractmethod
    def ingest(
        self,
        **fields: Any,
    ) -> tuple[Article, bool]: ...

    @abstractmethod
    def update(
        self,
        article: Article,
        **fields: Any,
    ) -> Article: ...

    @abstractmethod
    def delete_unlinked_older_than(
        self,
        cutoff: datetime,
    ) -> int:
        """Delete articles last seen before cutoff that no story links to.

        Returns how many were deleted.
        """
        ...

    @abstractmethod
    def get_translations(
        self,
        article_ids: List[uuid.UUID],
        language: str,
    ) -> dict[uuid.UUID, ArticleTranslation]:
        """The cached translations of these articles, by article id.
        Articles without a translation are left out."""
        ...

    @abstractmethod
    def save_translation(
        self,
        article_id: uuid.UUID,
        language: str,
        *,
        source_description: str,
        description: str,
    ) -> ArticleTranslation:
        """Insert or overwrite the translation for this article and language."""
        ...
