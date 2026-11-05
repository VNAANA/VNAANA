
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from Backend.Dal.models import ProviderSource as ProviderSourceModel
from Backend.Logic.domain.provider_source import ProviderSource
from Backend.Logic.ports.provider_source_repository import (
    ProviderSourceRepository as ProviderSourceRepositoryPort,
)


class ProviderSourceRepository(ProviderSourceRepositoryPort):

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _to_domain(source: ProviderSourceModel) -> ProviderSource:
        return ProviderSource(
            id=source.id,
            provider_id=source.provider_id,
            provider_name=source.provider.name,
            provider_domain=source.provider.domain,
            name=source.name,
            source_type=source.source_type,
            url=source.url,
            poll_interval_minutes=source.poll_interval_minutes,
            is_active=source.is_active,
            configuration=source.configuration or {},
        )

    async def get_active_sources(self) -> list[ProviderSource]:
        stmt = (
            select(ProviderSourceModel)
            .options(selectinload(ProviderSourceModel.provider))
            .where(ProviderSourceModel.is_active.is_(True))
            .order_by(ProviderSourceModel.name)
        )

        sources = self.db.scalars(stmt).all()

        return [self._to_domain(source) for source in sources]
