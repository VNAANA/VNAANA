"""The SQL that StoryRepository.list builds for a search.

No database needed: the session is a Mock, and the query it receives is
turned into PostgreSQL text so we can check its shape.
"""

from unittest.mock import Mock

import pytest
from sqlalchemy.dialects import postgresql

from Backend.Dal.repositories.story_repository import StoryRepository


@pytest.fixture
def db():
    db = Mock()
    # list() reads (story, articles_count) rows from execute(); no rows is enough here.
    db.execute.return_value = []
    return db


@pytest.fixture
def repository(db):
    return StoryRepository(db)


def statement(db):
    return db.execute.call_args.args[0]


def compiled(db):
    return statement(db).compile(dialect=postgresql.dialect())


def sql_sent(db) -> str:
    return str(compiled(db))


def values_sent(db) -> list:
    return list(compiled(db).params.values())


def where_sent(db) -> str:
    # Only the outer WHERE: the articles_count subquery has a WHERE of its own.
    return str(statement(db).whereclause.compile(dialect=postgresql.dialect()))


def test_without_search_terms_there_is_no_ilike(repository, db):
    repository.list(search_terms=None)

    assert "ILIKE" not in sql_sent(db)


def test_empty_search_terms_add_no_ilike(repository, db):
    repository.list(search_terms=[])

    assert "ILIKE" not in sql_sent(db)


def test_each_word_must_match_in_the_title(repository, db):
    repository.list(search_terms=["flood", "rotterdam"])

    sql = sql_sent(db)

    assert sql.count("stories.title ILIKE") == 2
    assert "stories.summary ILIKE" not in sql
    assert values_sent(db).count("%flood%") == 1
    assert values_sent(db).count("%rotterdam%") == 1
    # Every word must be in the title.
    where = where_sent(db)
    assert where.count(" AND ") == 1
    assert " OR " not in where


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("flood", "flood"),
        ("100%", "100\\%"),
        ("zeker_niet", "zeker\\_niet"),
        ("a\\b", "a\\\\b"),
        ("\\%", "\\\\\\%"),
    ],
)
def test_like_wildcards_are_escaped(term, expected):
    assert StoryRepository._escape_like(term) == expected


def test_the_query_tells_postgres_which_escape_character_is_used(repository, db):
    repository.list(search_terms=["100%"])

    assert "ESCAPE" in sql_sent(db)
    assert "%100\\%%" in values_sent(db)


def test_search_is_combined_with_status_and_tag(repository, db):
    repository.list(
        status="published",
        tag_ids=["00000000-0000-0000-0000-000000000001"],
        search_terms=["flood"],
    )

    where = where_sent(db)

    assert "stories.status" in where
    assert "story_tags.tag_id" in where
    assert "stories.title ILIKE" in where


def test_search_within_several_tags_only_looks_at_those_stories(repository, db):
    repository.list(
        tag_ids=["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"],
        search_terms=["flood"],
    )

    where = where_sent(db)

    # The tag subquery and the title search are both required (AND), not either.
    assert "stories.id IN (SELECT story_tags.story_id" in where
    assert "story_tags.tag_id IN" in where
    assert " AND stories.title ILIKE" in where


def test_pages_have_a_stable_order_and_the_requested_size(repository, db):
    repository.list(search_terms=["flood"], limit=20, offset=40)

    sql = sql_sent(db)
    params = compiled(db).params

    # last_updated_at can tie; the id keeps the order fixed between pages.
    assert "ORDER BY stories.last_updated_at DESC, stories.id" in sql
    assert 20 in params.values()
    assert 40 in params.values()
