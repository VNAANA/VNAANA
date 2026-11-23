
import asyncio
from typing import Any

from Backend.Dal.mock_data.provider_sources import MOCK_PROVIDER_SOURCES
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.mock_provider_source_repository import (
    MockProviderSourceRepository,
)
from Backend.Dal.repositories.provider_repository import ProviderRepository
from Backend.database import SessionLocal
from Backend.Logic.article_normalization_service import (
    ArticleNormalizationService,
)
from Backend.Logic.article_service import ArticleService
from Backend.Logic.news_gathering_service import NewsGatheringService
from Backend.Logic.provider_source_service import ProviderSourceService
from Backend.Logic.sources.rss_source import RSSSource


def _select_rss_sources() -> list[Any]:
    return [
        source
        for source in MOCK_PROVIDER_SOURCES
        if source.is_active
        and source.url
        and source.source_type == "rss"
    ]


def _create_news_gathering_service(
    source: Any,
    article_repository: ArticleRepository,
    provider_repository: ProviderRepository,
) -> NewsGatheringService:
    source_repository = MockProviderSourceRepository(sources=[source])
    provider_source_service = ProviderSourceService(source_repository)

    return NewsGatheringService(
        provider_source_service=provider_source_service,
        article_service=ArticleService(
            articles=article_repository,
            providers=provider_repository,
        ),
        article_repository=article_repository,
        provider_repository=provider_repository,
        source_handlers={"rss": RSSSource()},
        article_normalization_service=ArticleNormalizationService(),
    )


def _print_source_details(source: Any) -> None:
    print("=" * 80)
    print(f"Source: {source.name}")
    print(f"Provider: {source.provider_name}")
    print(f"URL: {source.url}")
    print(f"Provider ID: {source.provider_id}")


async def _process_source(
    source: Any,
    provider_repository: ProviderRepository,
    article_repository: ArticleRepository,
    db: Any,
    successful: list[str],
    failed: list[tuple[str, str]],
    skipped: list[tuple[str, str]],
) -> None:
    _print_source_details(source)

    try:
        provider = provider_repository.get(source.provider_id)

        if provider is None:
            message = (
                "Provider does not exist in the database: "
                f"{source.provider_id}"
            )
            print(f"SKIPPED: {message}")
            skipped.append((source.name, message))
            return

        print(f"Found provider: {provider.name} ({provider.domain})")

        news_gathering_service = _create_news_gathering_service(
            source,
            article_repository,
            provider_repository,
        )

        await news_gathering_service.gather()
        db.commit()

        print("SUCCESS: Gathering completed and committed.")
        successful.append(source.name)

    except Exception as exc:
        db.rollback()

        message = f"{type(exc).__name__}: {exc}"
        print(f"FAILED: {message}")
        failed.append((source.name, message))


def _print_summary(
    total: int,
    successful: list[str],
    failed: list[tuple[str, str]],
    skipped: list[tuple[str, str]],
) -> None:
    print("\n" + "=" * 80)
    print("RSS SOURCE TEST SUMMARY")
    print("=" * 80)
    print(f"Total selected: {total}")
    print(f"Successful:     {len(successful)}")
    print(f"Failed:         {len(failed)}")
    print(f"Skipped:        {len(skipped)}")

    if successful:
        print("\nSuccessful sources:")
        for name in successful:
            print(f"  [OK] {name}")

    if failed:
        print("\nFailed sources:")
        for name, error in failed:
            print(f"  [FAIL] {name}: {error}")

    if skipped:
        print("\nSkipped sources:")
        for name, reason in skipped:
            print(f"  [SKIP] {name}: {reason}")


async def main() -> None:
    sources = _select_rss_sources()

    print(f"Found {len(sources)} active RSS sources to test.\n")

    if not sources:
        print("No active RSS sources found.")
        return

    successful: list[str] = []
    failed: list[tuple[str, str]] = []
    skipped: list[tuple[str, str]] = []

    db = SessionLocal()

    try:
        provider_repository = ProviderRepository(db)
        article_repository = ArticleRepository(db)

        for source in sources:
            await _process_source(
                source,
                provider_repository,
                article_repository,
                db,
                successful,
                failed,
                skipped,
            )
    finally:
        db.close()

    _print_summary(len(sources), successful, failed, skipped)


if __name__ == "__main__":
    asyncio.run(main())
