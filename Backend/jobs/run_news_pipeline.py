
"""Entry point for the scheduled news-gathering pipeline."""

import asyncio
import logging

from Backend.config import get_settings
from Backend.database import SessionLocal
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.provider_repository import ProviderRepository
from Backend.Dal.repositories.provider_source_repository import (
    ProviderSourceRepository,
)
from Backend.Dal.repositories.story_repository import StoryRepository
from Backend.Dal.repositories.story_grouping import group_articles
from Backend.jobs.classify_grouped_stories import classify_grouped_stories
from Backend.Logic.article_service import ArticleService
from Backend.Logic.article_normalization_service import (
    ArticleNormalizationService,
)
from Backend.Logic.article_scraping_service import ArticleScrapingService
from Backend.Logic.cleanup_service import CleanupService
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
            limit=1000
        )

        db.commit()

        logger.info(
            "Article scraping finished: total=%s successful=%s failed=%s",
            scraping_results["total"],
            scraping_results["successful"],
            scraping_results["failed"],
        )

        # Phase 3: Delete stories and articles older than 30 days.
        # Runs after gathering, so articles still in a feed have just had
        # their last_seen_at refreshed and are kept.
        logger.info("Starting cleanup")

        cleanup_service = CleanupService(
            StoryRepository(db),
            article_repository,
        )

        cleanup_results = cleanup_service.delete_expired()

        db.commit()

        logger.info(
            "Cleanup finished: stories_deleted=%s articles_deleted=%s",
            cleanup_results["stories"],
            cleanup_results["articles"],
        )

        grouping_report = {}
        assigned = group_articles(db, report=grouping_report.update)
        db.commit()

        settings = get_settings()
        story_ids = [
            story["id"]
            for story in grouping_report.get("stories", [])
        ]

        if settings.genre_classification_pipeline_enabled and story_ids:
            try:
                classification_result = classify_grouped_stories(
                    story_ids,
                    session_factory=SessionLocal,
                )
                logger.info(
                    "Genre classification finished: processed=%s skipped=%s failed=%s",
                    len(classification_result["processed"]),
                    len(classification_result["skipped"]),
                    len(classification_result["failed"]),
                )
            except Exception:
                logger.exception("Genre classification failed")

        logger.info("News pipeline completed successfully: %s articles grouped", assigned)

    except Exception:
        db.rollback()
        logger.exception("News pipeline failed")
        raise

    finally:
        db.close()
        logger.info("Database session closed")


if __name__ == "__main__":
    main()
