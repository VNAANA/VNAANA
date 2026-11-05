import asyncio
import logging

from Backend.database import SessionLocal

from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.provider_repository import ProviderRepository

from Backend.Logic.article_normalization_service import (
    ArticleNormalizationService,
)
from Backend.Logic.article_service import ArticleService
from Backend.Logic.article_scraping_service import (
    ArticleScrapingService,
)
from Backend.Logic.news_gathering_service import (
    NewsGatheringService,
)
from Backend.Logic.provider_source_service import (
    ProviderSourceService,
)
from Backend.Logic.sources.rss_source import RSSSource


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


async def main() -> None:
    db = SessionLocal()

    try:
        logger.info("Starting news pipeline")

        article_repository = ArticleRepository(db)
        provider_repository = ProviderRepository(db)

        provider_source_repository = ProviderRepository(db)

        provider_source_service = ProviderSourceService(
            provider_source_repository
        )

        # 1. Gather news
        gathering_service = NewsGatheringService(
            provider_source_service=provider_source_service,
            article_service=ArticleService(
                articles=article_repository,
                providers=provider_repository,
            ),
            article_repository=article_repository,
            provider_repository=provider_repository,
            source_handlers={
                "rss": RSSSource(),
            },
            article_normalization_service=ArticleNormalizationService(),
        )

        logger.info("Starting news gathering")

        await gathering_service.gather()

        db.commit()

        logger.info("News gathering completed")

        # 2. Scrape article content
        scraping_service = ArticleScrapingService(
            article_repository=article_repository,
        )

        logger.info("Starting article scraping")

        results = scraping_service.scrape_pending_articles(
            limit=100,
        )

        db.commit()

        logger.info(
            "Scraping completed: total=%s successful=%s failed=%s",
            results["total"],
            results["successful"],
            results["failed"],
        )

        logger.info("News pipeline completed successfully")

    except Exception:
        db.rollback()
        logger.exception("News pipeline failed")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())