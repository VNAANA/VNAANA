from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from Backend.Dal.models import Story, StoryTag, Tag
from Backend.Dal.repositories.story_repository import StoryRepository


def test_genre_write_rechecks_content_and_preserves_committed_tags():
    engine = create_engine("sqlite://")
    try:
        for model in (Story, Tag, StoryTag):
            model.__table__.create(engine)
        with Session(engine) as session, session.begin():
            repo = StoryRepository(session)
            edited = repo.add(title="Old headline", context="Article")
            tagged = repo.add(title="Has a manual tag")
            eligible = repo.add(title="Still current")
            manual, automatic = Tag(name="Politics"), Tag(name="Science")
            session.add_all([manual, automatic])
            session.flush()
            manual_id, automatic_id = manual.id, automatic.id

        with Session(engine) as session, session.begin():
            repo = StoryRepository(session)
            repo.update(edited, title="New headline")
            repo.replace_tags(tagged, {manual_id: None})

        predictions = {automatic_id: Decimal("0.8")}
        with Session(engine) as session, session.begin():
            repo = StoryRepository(session)
            assert repo.add_genre_tags_if_current(edited, predictions) == "changed"
            assert repo.add_genre_tags_if_current(tagged, predictions) == "already_tagged"
            assert repo.add_genre_tags_if_current(eligible, predictions) == "saved"
            links = {(link.story_id, link.tag_id): link.relevance_score
                     for link in session.scalars(select(StoryTag))}
            assert links == {(tagged.id, manual_id): None,
                             (eligible.id, automatic_id): Decimal("0.8")}
            repo.replace_tags(eligible, {manual_id: None})
            repo.replace_tags(tagged, {})
            assert [(link.story_id, link.tag_id) for link in session.scalars(select(StoryTag))] == [
                (eligible.id, manual_id)
            ]
    finally:
        engine.dispose()


def test_replace_tags_preserves_pending_story_edit():
    engine = create_engine("sqlite://")
    try:
        for model in (Story, Tag, StoryTag):
            model.__table__.create(engine)
        with Session(engine, autoflush=False) as session, session.begin():
            repo = StoryRepository(session)
            story = repo.add(title="Original headline")
            stored_story = session.get(Story, story.id)
            stored_story.title = "Pending headline"

            repo.replace_tags(story, {})

            assert stored_story.title == "Pending headline"
        with Session(engine) as session:
            assert session.get(Story, story.id).title == "Pending headline"
    finally:
        engine.dispose()


def test_automatic_and_manual_tag_writes_lock_the_same_story_on_postgresql():
    import uuid
    from types import SimpleNamespace

    db = Mock()
    db.scalars.return_value = []
    db.execute.return_value.one_or_none.return_value = None
    repo = StoryRepository(db)
    story = SimpleNamespace(id=uuid.uuid4())

    repo.add_genre_tags_if_current(story, {})
    repo.replace_tags(story, {})
    automatic, manual = [call.args[0].compile(dialect=postgresql.dialect())
                         for call in db.execute.call_args_list]
    assert str(automatic) == str(manual)
    assert "FOR UPDATE" in str(automatic)
    assert list(automatic.params.values()) == [story.id]
