"""StoryRepository translation cache on an in-memory SQLite database."""

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from Backend.Dal.models import Base, Story, StoryTranslation
from Backend.Dal.repositories.story_repository import StoryRepository


@compiles(JSONB, "sqlite")
def compile_test_jsonb(type_, compiler, **kwargs):
    return "JSON"


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def story(db):
    story = Story(title="Titel", context="Context")
    db.add(story)
    db.commit()
    return story


def test_no_translation_yet(db, story):
    assert StoryRepository(db).get_translation(story.id, "en") is None


def test_saved_translation_can_be_read_back(db, story):
    repo = StoryRepository(db)

    saved = repo.save_translation(story.id, "en", title="Title", summary=None, context="Context EN")
    db.commit()
    loaded = repo.get_translation(story.id, "en")

    assert loaded == saved
    assert (loaded.title, loaded.summary, loaded.context) == ("Title", None, "Context EN")
    assert loaded.updated_at is not None
    assert repo.get_translation(story.id, "de") is None


def test_saving_again_overwrites_the_same_row(db, story):
    repo = StoryRepository(db)
    repo.save_translation(story.id, "en", title="Old", summary=None, context="Old context")
    db.commit()

    updated = repo.save_translation(story.id, "en", title="New", summary="Summary", context="New context")
    db.commit()

    assert (updated.title, updated.summary, updated.context) == ("New", "Summary", "New context")
    assert repo.get_translation(story.id, "en").title == "New"
    assert db.scalar(select(func.count()).select_from(StoryTranslation)) == 1
