"""Shared setup for the integration tests: the real, migrated Postgres database.

The tests run against their own database, `vnaana_integration`, on the local
Supabase Postgres (see tests/local_supabase.py). At the start of every test
run it is dropped, created again and built with `alembic upgrade head`, so the
tests see exactly the tables, constraints and seeded rows (default tags,
event weights) that production gets. The E2E tests use the default database
of the same server; the two never see each other's data.

Every test runs inside one transaction that is rolled back afterwards, so a
test starts from the freshly migrated database and leaves nothing behind.
`db.commit()` in a test only ends a savepoint inside that transaction.

Without local Supabase every integration test is skipped (in CI that's a
failure, because of REQUIRE_ALL_TESTS=1).
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from tests.local_supabase import migrate, read_local_supabase

INTEGRATION_DATABASE = "vnaana_integration"


@pytest.fixture(scope="session")
def integration_engine():
    server_url = make_url(read_local_supabase()["db_url"])

    # A fresh database for every run, so leftovers of an earlier run (or of
    # someone's own local testing) can't influence the results.
    with create_engine(server_url, isolation_level="AUTOCOMMIT").connect() as server:
        server.execute(text(f"DROP DATABASE IF EXISTS {INTEGRATION_DATABASE} WITH (FORCE)"))
        server.execute(text(f"CREATE DATABASE {INTEGRATION_DATABASE}"))

    url = server_url.set(database=INTEGRATION_DATABASE)
    migrate(url.render_as_string(hide_password=False))

    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(integration_engine):
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def new_session(db):
    """Another session on the same transaction, to read back what `db` stored
    without anything coming from db's memory."""
    sessions = []

    def make() -> Session:
        session = Session(
            bind=db.connection(),
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        sessions.append(session)
        return session

    yield make
    for session in sessions:
        session.close()
