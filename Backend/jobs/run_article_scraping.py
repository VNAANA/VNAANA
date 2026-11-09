from Backend.database import SessionLocal
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Logic.article_scraping_service import ArticleScrapingService


def main():
    db = SessionLocal()

    try:
        article_repository = ArticleRepository(db)

        scraping_service = ArticleScrapingService(
            article_repository
        )

        results = scraping_service.scrape_pending_articles(limit=100)

        db.commit()

        print("Scraping results:", results)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()