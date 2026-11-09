"""CleanupService: which cutoff it uses and in which order it deletes."""

from datetime import datetime, timedelta, timezone

import pytest

from Backend.Logic.Algorithm.decay import LIFETIME_DAYS
from Backend.Logic.cleanup_service import CleanupService

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


class RecordingStoryRepository:
    def __init__(self, calls: list, deleted: int = 0):
        self.calls = calls
        self.deleted = deleted

    def delete_older_than(self, cutoff):
        self.calls.append(("stories", cutoff))
        return self.deleted


class RecordingArticleRepository:
    def __init__(self, calls: list, deleted: int = 0):
        self.calls = calls
        self.deleted = deleted

    def delete_unlinked_older_than(self, cutoff):
        self.calls.append(("articles", cutoff))
        return self.deleted


@pytest.fixture
def calls() -> list:
    return []


def make_service(calls, stories_deleted=0, articles_deleted=0):
    return CleanupService(
        RecordingStoryRepository(calls, stories_deleted),
        RecordingArticleRepository(calls, articles_deleted),
    )


def test_cutoff_is_lifetime_days_before_now(calls):
    make_service(calls).delete_expired(now=NOW)

    expected = NOW - timedelta(days=LIFETIME_DAYS)
    assert [cutoff for _, cutoff in calls] == [expected, expected]


def test_lifetime_is_30_days():
    # Retention and the algorithm's decay share this number on purpose.
    assert LIFETIME_DAYS == 30


def test_stories_are_deleted_before_articles(calls):
    make_service(calls).delete_expired(now=NOW)

    assert [table for table, _ in calls] == ["stories", "articles"]


def test_returns_how_many_were_deleted(calls):
    result = make_service(calls, stories_deleted=3, articles_deleted=7).delete_expired(now=NOW)

    assert result == {"stories": 3, "articles": 7}


def test_without_now_it_uses_the_current_utc_time(calls):
    before = datetime.now(timezone.utc)
    make_service(calls).delete_expired()
    after = datetime.now(timezone.utc)

    cutoff = calls[0][1]
    assert before - timedelta(days=LIFETIME_DAYS) <= cutoff <= after - timedelta(days=LIFETIME_DAYS)
    assert cutoff.tzinfo is not None
