import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from Backend.Dal.models.base import Base

if TYPE_CHECKING:
    from Backend.Dal.models.provider_source import ProviderSource


class Provider(Base):
    """A news source (NOS, BBC, ...)."""

    __tablename__ = "providers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    domain: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    country_code: Mapped[str | None] = mapped_column(CHAR(2))
    reliability_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sources: Mapped[list["ProviderSource"]] = relationship(
        back_populates="provider", cascade="all, delete-orphan", passive_deletes=True
    )
