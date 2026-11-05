
"""Entry point for the scheduled news-gathering pipeline."""

import asyncio
import logging

from Backend.database import SessionLocal
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.provider_repository import ProviderRepository
from Backend.Dal.repositories.provider_source_repository import (
    ProviderSourceRepository,
)
from Backend.Logic.article_service import ArticleService
from Backend.Logic.article_normalization_service import (
    ArticleNormalizationService,
)
from Backend.Logic.article_scraping_service import ArticleScrapingService
from Backend.Logic.provider_source_service import ProviderSourceService
from Backend.Logic.news_gathering_service import NewsGatheringService
from Backend.Logic.sources.rss_source import RSSSource


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Starting news pipeline")

    db = SessionLocal()

    try:
        # Create repositories using the same database session.
        article_repository = ArticleRepository(db)
        provider_repository = ProviderRepository(db)
        provider_source_repository = ProviderSourceRepository(db)

        # Create services.
        provider_source_service = ProviderSourceService(
            provider_source_repository
        )

        article_service = ArticleService(
            article_repository,
            provider_repository,
        )

        normalization_service = ArticleNormalizationService()

        news_gathering_service = NewsGatheringService(
            provider_source_service=provider_source_service,
            article_service=article_service,
            article_repository=article_repository,
            provider_repository=provider_repository,
            source_handlers={
                "rss": RSSSource(),
            },
            article_normalization_service=normalization_service,
        )

        # Phase 1: Fetch feeds and ingest articles.
        logger.info("Starting article gathering")

        asyncio.run(news_gathering_service.gather())

        db.commit()
        logger.info("Article gathering committed successfully")

        # Phase 2: Scrape content for articles that have not been scraped.
        logger.info("Starting article scraping")

        scraping_service = ArticleScrapingService(article_repository)

        scraping_results = scraping_service.scrape_pending_articles(
            limit=100
        )

        db.commit()

        logger.info(
            "Article scraping finished: total=%s successful=%s failed=%s",
            scraping_results["total"],
            scraping_results["successful"],
            scraping_results["failed"],
        )

        logger.info("News pipeline completed successfully")

    except Exception:
        db.rollback()
        logger.exception("News pipeline failed")
        raise

    finally:
        db.close()
        logger.info("Database session closed")


if __name__ == "__main__":
    main()
