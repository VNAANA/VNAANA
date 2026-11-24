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


def test_each_word_must_match_in_title_or_summary(repository, db):
    repository.list(search_terms=["flood", "rotterdam"])

    sql = sql_sent(db)

    assert sql.count("stories.title ILIKE") == 2
    assert sql.count("stories.summary ILIKE") == 2
    assert values_sent(db).count("%flood%") == 2
    assert values_sent(db).count("%rotterdam%") == 2
    # Words are ANDed together, the two columns per word are ORed.
    where = where_sent(db)
    assert where.count(" AND ") == 1
    assert where.count(" OR ") == 2


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
