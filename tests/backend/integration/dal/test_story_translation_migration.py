"""Exercise translation data migration locally without contacting PostgreSQL."""

from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def migrated(monkeypatch):
    migration = import_module(
        "Backend.Dal.migrations.versions.b83c1e5a902d_create_story_translations"
    )
    engine = create_engine("sqlite://")
    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("""CREATE TABLE stories (
            id UUID PRIMARY KEY, title TEXT NOT NULL,
            eng_title TEXT, eng_summary TEXT, eng_context TEXT
        )"""))
        connection.execute(text("""INSERT INTO stories VALUES
            ('story-a', 'Original A', 'English A', NULL, 'English context'),
            ('story-b', 'Original B', NULL, NULL, NULL),
            ('story-c', 'Original C', NULL, 'Partial summary', NULL)
        """))
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        yield connection, migration
    engine.dispose()


def test_backfill_constraints_and_cascade(migrated):
    db, _ = migrated
    rows = db.execute(text("SELECT story_id, language, title, summary, context, updated_at FROM story_translations ORDER BY story_id")).all()
    assert len(rows) == 2
    assert tuple(rows[0][:5]) == ('story-a', 'en', 'English A', None, 'English context')
    assert rows[1].summary == 'Partial summary'
    assert all(row.updated_at is not None for row in rows)
    assert 'eng_title' not in {c['name'] for c in inspect(db).get_columns('stories')}
    with pytest.raises(IntegrityError):
        db.execute(text("INSERT INTO story_translations (story_id, language) VALUES ('story-a', 'en')"))
    db.execute(text("INSERT INTO story_translations (story_id, language) VALUES ('story-a', 'vi')"))
    db.execute(text("DELETE FROM stories WHERE id = 'story-a'"))
    assert db.scalar(text("SELECT count(*) FROM story_translations WHERE story_id = 'story-a'")) == 0


def test_downgrade_restores_english_content(migrated):
    db, migration = migrated
    migration.downgrade()
    assert 'story_translations' not in inspect(db).get_table_names()
    assert db.execute(text("SELECT title, eng_title, eng_context FROM stories WHERE id='story-a'")).one() == (
        'Original A', 'English A', 'English context'
    )
    assert db.scalar(text("SELECT eng_summary FROM stories WHERE id='story-c'")) == 'Partial summary'


def test_downgrade_refuses_to_lose_other_languages(migrated):
    db, migration = migrated
    db.execute(text("INSERT INTO story_translations (story_id, language, title) VALUES ('story-a', 'vi', 'Vietnamese title')"))
    with pytest.raises(RuntimeError, match='non-English'):
        migration.downgrade()
    assert db.scalar(text("SELECT title FROM story_translations WHERE language='vi'")) == 'Vietnamese title'
