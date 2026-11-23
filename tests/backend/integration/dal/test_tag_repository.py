"""TagRepository on an in-memory SQLite database (setup in ../conftest.py)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from Backend.Dal.models import Tag as TagModel
from Backend.Dal.repositories.tag_repository import TagRepository


@pytest.fixture
def repo(db) -> TagRepository:
    return TagRepository(db)


def test_an_added_tag_gets_an_id_and_can_be_found_again(db, repo):
    tag = repo.add("Science")
    db.commit()
    db.expire_all()

    assert tag.id is not None
    assert repo.get(tag.id) == tag


def test_an_unknown_id_gives_none(repo):
    assert repo.get(uuid.uuid4()) is None


def test_tag_names_are_unique(db, repo):
    repo.add("Sport")
    db.commit()

    with pytest.raises(IntegrityError):
        repo.add("Sport")


def test_get_many_returns_only_the_asked_tags(db, repo):
    sport, music, _ = repo.add("Sport"), repo.add("Music"), repo.add("Tech")
    db.commit()

    tags = repo.get_many([sport.id, music.id, uuid.uuid4()])

    assert {tag.name for tag in tags} == {"Sport", "Music"}


def test_get_many_with_no_ids_gives_nothing(repo):
    assert repo.get_many([]) == []


def test_a_tag_can_be_found_by_name(db, repo):
    science = repo.add("Science")
    db.commit()

    assert repo.get_by_name("Science") == science
    assert repo.get_by_name("Politics") is None


def test_all_tags_are_listed_by_name(db, repo):
    for name in ("Tech", "Music", "Sport"):
        db.add(TagModel(name=name))
    db.commit()

    assert [tag.name for tag in repo.list_all()] == ["Music", "Sport", "Tech"]


def test_no_tags_gives_an_empty_list(repo):
    assert repo.list_all() == []
