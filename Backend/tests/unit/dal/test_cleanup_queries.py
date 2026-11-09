"""The DELETE statements the repositories send for the hourly cleanup.

No database needed: the session is a Mock, and the statement it receives is
turned into PostgreSQL text so we can check its shape.
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository

CUTOFF = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db():
    db = Mock()
    db.execute.return_value.rowcount = 4
    return db


def compiled(db):
    stmt = db.execute.call_args.args[0]
    return stmt.compile(dialect=postgresql.dialect())


def normalized_sql(db) -> str:
    return " ".join(str(compiled(db)).split())


def test_stories_are_deleted_by_last_updated_at(db):
    StoryRepository(db).delete_older_than(CUTOFF)

    sql = normalized_sql(db)

    assert sql.startswith("DELETE FROM stories")
    assert "stories.last_updated_at < " in sql
    assert list(compiled(db).params.values()) == [CUTOFF]


def test_story_delete_returns_the_rowcount(db):
    assert StoryRepository(db).delete_older_than(CUTOFF) == 4


def test_articles_are_deleted_by_last_seen_at(db):
    ArticleRepository(db).delete_unlinked_older_than(CUTOFF)

    sql = normalized_sql(db)

    assert sql.startswith("DELETE FROM articles")
    assert "articles.last_seen_at < " in sql
    assert "articles.last_updated_at" not in sql
    assert list(compiled(db).params.values()) == [CUTOFF]


def test_articles_still_linked_to_a_story_are_kept(db):
    ArticleRepository(db).delete_unlinked_older_than(CUTOFF)

    sql = normalized_sql(db)

    assert "NOT (EXISTS (SELECT" in sql
    assert "FROM story_articles" in sql
    assert "story_articles.article_id = articles.id" in sql


def test_article_delete_returns_the_rowcount(db):
    assert ArticleRepository(db).delete_unlinked_older_than(CUTOFF) == 4
