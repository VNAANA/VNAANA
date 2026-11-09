import calendar
import feedparser

from datetime import datetime, timedelta, timezone

from Backend.Logic.domain.article import RawArticle
from Backend.Logic.domain.provider_source import ProviderSource
from Backend.Logic.sources.news_source import NewsSource


class RSSSource(NewsSource):

    def __init__(self, max_age_days: int = 30):
        self.max_age_days = max_age_days

    async def fetch(
        self,
        source: ProviderSource,
    ) -> list[RawArticle]:

        feed = feedparser.parse(source.url)

        if getattr(feed, "bozo", False):
            print(
                f"Warning: feed parsing issue for {source.name}: "
                f"{getattr(feed, 'bozo_exception', 'unknown error')}"
            )

        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=self.max_age_days
        )

        articles: list[RawArticle] = []
        skipped_old = 0

        for entry in feed.entries:
            updated = entry.get("updated_parsed")
            parsed_date = entry.get("published_parsed") or updated

            published_at = None

            if parsed_date:
                published_at = datetime.fromtimestamp(
                    calendar.timegm(parsed_date),
                    tz=timezone.utc,
                )

                # Skip old articles only when a date is available.
                if published_at < cutoff_date:
                    skipped_old += 1
                    continue

            last_updated_at = (
                datetime.fromtimestamp(
                    calendar.timegm(updated),
                    tz=timezone.utc,
                )
                if updated else None
            )

            articles.append(
                RawArticle(
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    description=(
                        entry.get("summary")
                        or entry.get("description")
                    ),
                    author=(
                        entry.get("author")
                        or entry.get("dc_creator")
                    ),
                    language=(
                        entry.get("language")
                        or feed.feed.get("language")
                    ),
                    published_at=published_at,
                    last_updated_at=last_updated_at,
                    provider_id=source.provider_id,
                )
            )

        print(
            f"RSS source {source.name}: "
            f"accepted={len(articles)}, "
            f"skipped_old={skipped_old}, "
            f"skipped_without_date=0"
        )

        return articles
