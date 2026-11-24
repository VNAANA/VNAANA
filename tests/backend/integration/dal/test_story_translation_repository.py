"""StoryRepository translation cache on the real migrated Postgres database (setup in ../conftest.py)."""

import pytest
from sqlalchemy import func, select

from Backend.Dal.models import Story, StoryTranslation
from Backend.Dal.repositories.story_repository import StoryRepository


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


def test_the_lead_article_description_is_saved_with_the_story(db, story):
    repo = StoryRepository(db)

    repo.save_translation(
        story.id, "en", title="Title", summary=None, context="Context EN",
        description="Description",
    )
    db.commit()
    loaded = repo.get_translation(story.id, "en")

    assert loaded.description == "Description"
    assert repo.get_translations([story.id], "en")[story.id] == loaded


def test_saving_without_a_description_clears_the_old_one(db, story):
    repo = StoryRepository(db)
    repo.save_translation(
        story.id, "en", title="Title", summary=None, context=None,
        description="Description",
    )
    db.commit()

    updated = repo.save_translation(story.id, "en", title="Title", summary=None, context=None)

    assert updated.description is None
