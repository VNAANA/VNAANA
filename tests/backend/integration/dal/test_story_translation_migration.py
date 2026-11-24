"""The story_translations migration, up and down, on real Postgres.

The migration needs the OLD stories table (with eng_title, eng_summary and
eng_context), which the migrated test database no longer has. So each test
builds that old table in a throwaway schema, runs the migration there, and
rolls everything back afterwards; Postgres can roll back table changes too.
"""

import uuid
from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

SCHEMA = "translation_migration_test"
STORY_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
STORY_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")
STORY_C = uuid.UUID("00000000-0000-0000-0000-00000000000c")


@pytest.fixture
def migrated(integration_engine, monkeypatch):
    migration = import_module(
        "Backend.Dal.migrations.versions.b83c1e5a902d_create_story_translations"
    )
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        # Only for this transaction: unqualified table names now mean the throwaway schema.
        connection.execute(text(f"SET LOCAL search_path TO {SCHEMA}"))
        connection.execute(text("""CREATE TABLE stories (
            id UUID PRIMARY KEY, title TEXT NOT NULL,
            eng_title TEXT, eng_summary TEXT, eng_context TEXT
        )"""))
        connection.execute(
            text("""INSERT INTO stories VALUES
                (:a, 'Original A', 'English A', NULL, 'English context'),
                (:b, 'Original B', NULL, NULL, NULL),
                (:c, 'Original C', NULL, 'Partial summary', NULL)
            """),
            {"a": STORY_A, "b": STORY_B, "c": STORY_C},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        try:
            yield connection, migration
        finally:
            transaction.rollback()


def tables(db) -> set[str]:
    return set(inspect(db).get_table_names(schema=SCHEMA))


def story_columns(db) -> set[str]:
    return {column["name"] for column in inspect(db).get_columns("stories", schema=SCHEMA)}


def test_backfill_constraints_and_cascade(migrated):
    db, _ = migrated
    rows = db.execute(text("SELECT story_id, language, title, summary, context, updated_at FROM story_translations ORDER BY story_id")).all()
    assert len(rows) == 2
    assert tuple(rows[0][:5]) == (STORY_A, "en", "English A", None, "English context")
    assert rows[1].story_id == STORY_C
    assert rows[1].summary == "Partial summary"
    assert all(row.updated_at is not None for row in rows)
    assert "eng_title" not in story_columns(db)
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("INSERT INTO story_translations (story_id, language) VALUES (:a, 'en')"), {"a": STORY_A})
    db.execute(text("INSERT INTO story_translations (story_id, language) VALUES (:a, 'vi')"), {"a": STORY_A})
    db.execute(text("DELETE FROM stories WHERE id = :a"), {"a": STORY_A})
    assert db.scalar(text("SELECT count(*) FROM story_translations WHERE story_id = :a"), {"a": STORY_A}) == 0


def test_downgrade_restores_english_content(migrated):
    db, migration = migrated
    migration.downgrade()
    assert "story_translations" not in tables(db)
    assert db.execute(text("SELECT title, eng_title, eng_context FROM stories WHERE id = :a"), {"a": STORY_A}).one() == (
        "Original A", "English A", "English context"
    )
    assert db.scalar(text("SELECT eng_summary FROM stories WHERE id = :c"), {"c": STORY_C}) == "Partial summary"


def test_downgrade_refuses_to_lose_other_languages(migrated):
    db, migration = migrated
    db.execute(
        text("INSERT INTO story_translations (story_id, language, title) VALUES (:a, 'vi', 'Vietnamese title')"),
        {"a": STORY_A},
    )
    with pytest.raises(RuntimeError, match="non-English"):
        migration.downgrade()
    assert db.scalar(text("SELECT title FROM story_translations WHERE language = 'vi'")) == "Vietnamese title"


def test_the_throwaway_schema_is_gone_afterwards(integration_engine):
    # Runs after the others: nothing of the old-style tables may be left behind.
    with integration_engine.connect() as connection:
        assert SCHEMA not in inspect(connection).get_schema_names()
