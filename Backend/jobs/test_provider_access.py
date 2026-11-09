
import logging
from collections import defaultdict

import requests

from Backend.database import SessionLocal
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.provider_repository import ProviderRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER_AGENT = (
    "VNAANA/1.0 "
    "(https://github.com/vnaana/VNAANA)"
)

ARTICLES_PER_PROVIDER = 3
TIMEOUT = 15


def main():
    db = SessionLocal()

    try:
        article_repository = ArticleRepository(db)
        provider_repository = ProviderRepository(db)

        # Retrieve all providers.
        providers = provider_repository.list_all()

        results = defaultdict(
            lambda: {
                "tested": 0,
                "success": 0,
                "forbidden": 0,
                "not_found": 0,
                "rate_limited": 0,
                "other_errors": 0,
            }
        )

        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        }

        for provider in providers:
            articles = article_repository.list(
                provider_id=provider.id,
                limit=ARTICLES_PER_PROVIDER,
            )

            if not articles:
                logger.info(
                    "No articles found for %s",
                    provider.name,
                )
                continue

            logger.info(
                "Testing provider: %s (%d articles)",
                provider.name,
                len(articles),
            )

            for article in articles:
                try:
                    response = requests.get(
                        article.canonical_url,
                        headers=headers,
                        timeout=TIMEOUT,
                        allow_redirects=True,
                    )

                    status = response.status_code

                    results[provider.name]["tested"] += 1

                    if status == 200:
                        results[provider.name]["success"] += 1
                    elif status == 403:
                        results[provider.name]["forbidden"] += 1
                    elif status == 404:
                        results[provider.name]["not_found"] += 1
                    elif status == 429:
                        results[provider.name]["rate_limited"] += 1
                    else:
                        results[provider.name]["other_errors"] += 1

                    logger.info(
                        "%s | HTTP %s | %s",
                        provider.name,
                        status,
                        article.canonical_url,
                    )

                except requests.RequestException as exc:
                    results[provider.name]["tested"] += 1
                    results[provider.name]["other_errors"] += 1

                    logger.warning(
                        "%s | Request error: %s",
                        provider.name,
                        exc,
                    )

        print("\n========== PROVIDER ACCESS REPORT ==========")

        for provider_name, stats in results.items():
            print(f"\n{provider_name}")
            for key, value in stats.items():
                print(f"  {key}: {value}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
