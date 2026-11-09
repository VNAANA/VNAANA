import calendar
import feedparser

from datetime import datetime, timedelta, timezone

from Backend.Logic.domain.article import RawArticle
from Backend.Logic.domain.provider_source import ProviderSource
from Backend.Logic.sources.news_source import NewsSource


class RSSSource(NewsSource):

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

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        articles: list[RawArticle] = []
        skipped_old = 0
        skipped_without_date = 0

        for entry in feed.entries:
            updated = entry.get("updated_parsed")
            parsed_date = (
                entry.get("published_parsed")
                or updated
            )

            # Skip articles without a publication or update date.
            if not parsed_date:
                skipped_without_date += 1
                continue

            published_at = datetime.fromtimestamp(
                calendar.timegm(parsed_date),
                tz=timezone.utc,
            )

            # Skip articles older than 30 days.
            if published_at < cutoff_date:
                skipped_old += 1
                continue

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
                    last_updated_at=(
                        datetime.fromtimestamp(
                            calendar.timegm(updated),
                            tz=timezone.utc,
                        )
                        if updated else None
                    ),
                    provider_id=source.provider_id,
                )
            )

        print(
            f"RSS source {source.name}: "
            f"accepted={len(articles)}, "
            f"skipped_old={skipped_old}, "
            f"skipped_without_date={skipped_without_date}"
        )

        return articles