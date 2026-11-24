"""The migration that drops article_translations, up and down, on real Postgres.

Like the other translation migration tests: each test builds the minimal
tables in a throwaway schema, runs the migration there, and rolls everything
back afterwards.
"""

import uuid
from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text

SCHEMA = "drop_article_translations_migration_test"
STORY = uuid.UUID("00000000-0000-0000-0000-0000000000b1")
MIGRATION = "Backend.Dal.migrations.versions.f2b8d4c07a15_drop_article_translations"


@pytest.fixture
def migrated(integration_engine, monkeypatch):
    migration = import_module(MIGRATION)
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        # Only for this transaction: unqualified table names now mean the throwaway schema.
        connection.execute(text(f"SET LOCAL search_path TO {SCHEMA}"))
        connection.execute(text("CREATE TABLE articles (id UUID PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE story_translations (story_id UUID, language VARCHAR, "
                "title TEXT, description TEXT, PRIMARY KEY (story_id, language))"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE article_translations (article_id UUID, language VARCHAR, "
                "source_description TEXT NOT NULL, description TEXT NOT NULL, "
                "PRIMARY KEY (article_id, language))"
            )
        )
        connection.execute(
            text("INSERT INTO story_translations VALUES (:s, 'en', 'Title', 'Description')"),
            {"s": STORY},
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        try:
            yield connection, migration
        finally:
            transaction.rollback()


def tables(db):
    return set(inspect(db).get_table_names(schema=SCHEMA))


def test_it_is_the_newest_migration():
    assert import_module(MIGRATION).down_revision == "c4e8f2a6d913"


def test_upgrade_drops_only_article_translations(migrated):
    db, _ = migrated

    assert "article_translations" not in tables(db)
    # Story translations, with their descriptions, are untouched.
    row = db.execute(text("SELECT title, description FROM story_translations")).one()
    assert tuple(row) == ("Title", "Description")


def test_downgrade_brings_article_translations_back(migrated):
    db, migration = migrated

    migration.downgrade()

    assert {"article_translations", "story_translations"} <= tables(db)


def test_the_throwaway_schema_is_gone_afterwards(integration_engine):
    with integration_engine.connect() as connection:
        assert SCHEMA not in inspect(connection).get_schema_names()
