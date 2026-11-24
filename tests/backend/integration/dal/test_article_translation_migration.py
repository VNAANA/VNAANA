"""The article_translations migration, up and down, on real Postgres.

Like the story_translations migration test: each test builds a minimal
articles table in a throwaway schema, runs the migration there, and rolls
everything back afterwards.
"""

import uuid
from importlib import import_module

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

SCHEMA = "article_translation_migration_test"
ARTICLE = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
MIGRATION = "Backend.Dal.migrations.versions.c4e8f2a61d97_create_article_translations"


@pytest.fixture
def migrated(integration_engine, monkeypatch):
    migration = import_module(MIGRATION)
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        # Only for this transaction: unqualified table names now mean the throwaway schema.
        connection.execute(text(f"SET LOCAL search_path TO {SCHEMA}"))
        connection.execute(text("CREATE TABLE articles (id UUID PRIMARY KEY, description TEXT)"))
        connection.execute(
            text("INSERT INTO articles VALUES (:a, 'Beschrijving')"), {"a": ARTICLE}
        )
        monkeypatch.setattr(migration, "op", Operations(MigrationContext.configure(connection)))
        migration.upgrade()
        try:
            yield connection, migration
        finally:
            transaction.rollback()


def insert(db, language, source_description, description):
    db.execute(
        text(
            "INSERT INTO article_translations (article_id, language, source_description, description) "
            "VALUES (:a, :language, :source, :description)"
        ),
        {"a": ARTICLE, "language": language, "source": source_description, "description": description},
    )


def test_it_follows_the_story_translation_migrations():
    assert import_module(MIGRATION).down_revision == "a3d5e7f91b20"


def test_constraints_defaults_and_cascade(migrated):
    db, _ = migrated
    insert(db, "en", "Beschrijving", "Description")
    assert db.scalar(text("SELECT updated_at FROM article_translations")) is not None

    # One translation per article and language.
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, "en", "Beschrijving", "Another description")
    # Without the original text the cache can't tell when it is outdated.
    with pytest.raises(IntegrityError), db.begin_nested():
        insert(db, "de", None, "Beschreibung")

    db.execute(text("DELETE FROM articles WHERE id = :a"), {"a": ARTICLE})
    assert db.scalar(text("SELECT count(*) FROM article_translations")) == 0


def test_downgrade_drops_only_the_translations(migrated):
    db, migration = migrated
    migration.downgrade()
    tables = set(inspect(db).get_table_names(schema=SCHEMA))
    assert "article_translations" not in tables
    assert "articles" in tables


def test_the_throwaway_schema_is_gone_afterwards(integration_engine):
    with integration_engine.connect() as connection:
        assert SCHEMA not in inspect(connection).get_schema_names()
