"""Translated article descriptions, with one translation per article and language."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Backend.Dal.models.base import Base

if TYPE_CHECKING:
    from Backend.Dal.models.article import Article


class ArticleTranslation(Base):
    __tablename__ = "article_translations"

    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("articles.id", ondelete="CASCADE"),
        primary_key=True,
    )
    language: Mapped[str] = mapped_column(String, primary_key=True)
    # The original description this translation was made from. When the
    # article's description no longer matches, the translation is outdated.
    source_description: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # SQLAlchemy updates this on writes; raw SQL writers must set it explicitly.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    article: Mapped["Article"] = relationship(back_populates="translations")
