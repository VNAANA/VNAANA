"""Shared setup for the integration tests: a fresh in-memory SQLite database.

Every test gets its own empty database with all tables created from the
models, and foreign keys switched on (SQLite has them off by default), so
ON DELETE CASCADE / SET NULL behave like they do on Postgres.

Older test files still build their own database; a `db` fixture in a test
file wins over this one.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from Backend.Dal.models import Base


@compiles(JSONB, "sqlite")
def compile_jsonb_for_sqlite(type_, compiler, **kwargs):
    # SQLite has no JSONB; plain JSON stores the same data for these tests.
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
