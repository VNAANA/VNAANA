"""TagRepository on the real migrated Postgres database (setup in ../conftest.py).

The migrations seed the default tags (Politics, Technology, ... Science), so
the tests use names that aren't among them and never expect an empty table.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from Backend.Dal.repositories.tag_repository import TagRepository

DEFAULT_TAGS = {
    "Politics", "Technology", "Sports", "Climate", "Economy", "Health",
    "Entertainment", "Social Issues", "Culture", "Science", "Domestic", "International",
}


@pytest.fixture
def repo(db) -> TagRepository:
    return TagRepository(db)


def test_the_migrations_add_the_default_tags(repo):
    assert {tag.name for tag in repo.list_all()} == DEFAULT_TAGS


def test_an_added_tag_gets_an_id_and_can_be_found_again(db, repo):
    tag = repo.add("Test topic")
    db.commit()
    db.expire_all()

    assert tag.id is not None
    assert repo.get(tag.id) == tag


def test_an_unknown_id_gives_none(repo):
    assert repo.get(uuid.uuid4()) is None


def test_tag_names_are_unique(db, repo):
    with pytest.raises(IntegrityError):
        repo.add("Politics")  # already there from the migrations


def test_get_many_returns_only_the_asked_tags(db, repo):
    first, second, _ = repo.add("Test A"), repo.add("Test B"), repo.add("Test C")
    db.commit()

    tags = repo.get_many([first.id, second.id, uuid.uuid4()])

    assert {tag.name for tag in tags} == {"Test A", "Test B"}


def test_get_many_with_no_ids_gives_nothing(repo):
    assert repo.get_many([]) == []


def test_a_tag_can_be_found_by_name(db, repo):
    added = repo.add("Test topic")
    db.commit()

    assert repo.get_by_name("Test topic") == added
    assert repo.get_by_name("Science").name == "Science"
    assert repo.get_by_name("Not a tag") is None


def test_all_tags_are_listed_by_name(db, repo):
    for name in ("Zz test", "Aa test"):
        repo.add(name)
    db.commit()

    names = [tag.name for tag in repo.list_all()]

    assert names == sorted(names)
    assert {"Zz test", "Aa test"} <= set(names)
