import calendar
import re
from datetime import datetime, timedelta, timezone
from html import unescape
from urllib.parse import urljoin, urlparse

import feedparser
from Backend.Logic.domain.article import RawArticle
from Backend.Logic.domain.provider_source import ProviderSource
from Backend.Logic.sources.news_source import NewsSource


class RSSSource(NewsSource):

    def __init__(self, max_age_days: int = 30):
        self.max_age_days = max_age_days

    
    @staticmethod
    def _resolve_image_url(url: str, feed_url: str) -> str:
        return urljoin(feed_url, unescape(url.strip()))

    @staticmethod
    def _extract_media_content(entry, feed_url: str) -> str | None:
        for media in entry.get("media_content", []) or []:
            url = media.get("url")
            media_type = media.get("type", "").lower()
            medium = media.get("medium", "").lower()

            if url and (
                media_type.startswith("image/")
                or medium == "image"
            ):
                return RSSSource._resolve_image_url(url, feed_url)

        return None

    @staticmethod
    def _extract_media_thumbnail(entry, feed_url: str) -> str | None:
        for media in entry.get("media_thumbnail", []) or []:
            url = media.get("url")

            if url:
                return RSSSource._resolve_image_url(url, feed_url)

        return None

    @staticmethod
    def _extract_enclosure_image(entry, feed_url: str) -> str | None:
        image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif")

        for enclosure in entry.get("enclosures", []) or []:
            url = enclosure.get("href") or enclosure.get("url")
            media_type = enclosure.get("type", "").lower()

            if not url:
                continue

            is_image = (
                media_type.startswith("image/")
                or urlparse(url).path.lower().endswith(image_extensions)
            )

            if is_image:
                return RSSSource._resolve_image_url(url, feed_url)

        return None

    @staticmethod
    def _extract_custom_image(entry, feed_url: str) -> str | None:
        for field in ("image", "image_url"):
            image = entry.get(field)

            if isinstance(image, str) and image.strip():
                return RSSSource._resolve_image_url(image, feed_url)

            if isinstance(image, dict):
                url = image.get("href") or image.get("url")

                if url:
                    return RSSSource._resolve_image_url(url, feed_url)

        return None

    @staticmethod
    def _extract_html_image(entry, feed_url: str) -> str | None:
        for field in ("content", "summary", "description"):
            value = entry.get(field)

            if isinstance(value, list):
                html = " ".join(
                    item.get("value", "")
                    for item in value
                    if isinstance(item, dict)
                )
            elif isinstance(value, dict):
                html = value.get("value", "")
            else:
                html = value or ""

            image_url = RSSSource._extract_image_from_html(
                html,
                feed_url,
            )

            if image_url:
                return image_url

        return None

    @staticmethod
    def _extract_image_url(entry, feed_url: str) -> str | None:
        """Extract an image URL using supported RSS image formats."""
        extractors = (
            RSSSource._extract_media_content,
            RSSSource._extract_media_thumbnail,
            RSSSource._extract_enclosure_image,
            RSSSource._extract_custom_image,
            RSSSource._extract_html_image,
        )

        for extractor in extractors:
            image_url = extractor(entry, feed_url)

            if image_url:
                return image_url

        return None


    @staticmethod
    def _extract_image_from_html(
        html: str,
        feed_url: str,
    ) -> str | None:

        if not isinstance(html, str) or not html:
            return None

        html = unescape(html)

        # Standard src and lazy-loaded data-src
        match = re.search(
            r'<img\b[^>]*?\b(?:src|data-src)\s*=\s*["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )

        if match:
            return urljoin(feed_url, match.group(1).strip())

        # srcset: use the first candidate
        match = re.search(
            r'\bsrcset\s*=\s*["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )

        if match:
            first_image = match.group(1).split(",")[0].strip().split()[0]

            if first_image:
                return urljoin(feed_url, first_image)

        return None


    @staticmethod
    def _extract_image_from_html(html: str, feed_url: str) -> str | None:
        if not html:
            return None

        html = unescape(html)

        match = re.search(
            r'<img[^>]+src=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )

        if match:
            return urljoin(feed_url, match.group(1))

        return None

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
                    img_url=self._extract_image_url(entry, source.url),
                )
            )

        print(
            f"RSS source {source.name}: "
            f"accepted={len(articles)}, "
            f"skipped_old={skipped_old}, "
            f"skipped_without_date=0"
        )

        return articles
