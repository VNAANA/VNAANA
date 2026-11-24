"""ArticleRepository on the real migrated Postgres database (setup in ../conftest.py).

Ingestion is already covered in test_dal.py; this file covers the rest.
"""

import uuid
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from Backend.Dal.models import (
    Article as ArticleModel,
    EngagementEvent,
    Provider,
    Story,
    StoryArticle,
)
from Backend.Dal.repositories.article_repository import ArticleRepository

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def provider(db) -> Provider:
    provider = Provider(name="NOS", domain="nos.nl", country_code="NL", reliability_status="verified")
    db.add(provider)
    db.commit()
    return provider


@pytest.fixture
def repo(db) -> ArticleRepository:
    return ArticleRepository(db)


def add_article(db, provider, url=None, **fields) -> ArticleModel:
    fields.setdefault("title", "Title")
    fields.setdefault("description", "Description")
    article = ArticleModel(
        provider_id=provider.id,
        canonical_url=url or f"https://nos.nl/{uuid.uuid4()}",
        **fields,
    )
    db.add(article)
    db.commit()
    return article


def stored_article_ids(db) -> set[uuid.UUID]:
    db.commit()
    db.expire_all()
    return set(db.scalars(select(ArticleModel.id)))


# ---- adding and finding ------------------------------------------------------------


def test_an_added_article_can_be_found_again(db, repo, provider):
    added = repo.add(provider_id=provider.id, canonical_url="https://nos.nl/a", title="News", language="nl")
    db.commit()
    db.expire_all()

    found = repo.get(added.id)

    assert found.canonical_url == "https://nos.nl/a"
    assert (found.title, found.language) == ("News", "nl")
    assert found.is_scraped is False  # default from the model


def test_an_article_comes_back_with_its_provider(db, repo, provider):
    article = add_article(db, provider)

    found = repo.get(article.id)

    assert found.provider.id == provider.id
    assert (found.provider.name, found.provider.domain) == ("NOS", "nos.nl")


def test_an_unknown_article_gives_none(repo):
    assert repo.get(uuid.uuid4()) is None


def test_an_article_can_be_found_by_canonical_url(db, repo, provider):
    article = add_article(db, provider, "https://nos.nl/b")

    assert repo.get_by_canonical_url("https://nos.nl/b").id == article.id
    assert repo.get_by_canonical_url("https://nos.nl/missing") is None


# ---- listing -----------------------------------------------------------------------


def test_list_can_filter_on_provider_and_language(db, repo, provider):
    bbc = Provider(name="BBC", domain="bbc.co.uk", reliability_status="verified")
    db.add(bbc)
    db.commit()
    dutch = add_article(db, provider, language="nl")
    add_article(db, provider, language="en")
    english_bbc = add_article(db, bbc, language="en")

    assert [a.id for a in repo.list(provider_id=provider.id, language="nl")] == [dutch.id]
    assert [a.id for a in repo.list(provider_id=bbc.id)] == [english_bbc.id]
    assert len(repo.list(language="en")) == 2


def test_list_shows_newest_published_first_and_unpublished_last(db, repo, provider):
    old = add_article(db, provider, published_at=NOW - timedelta(days=2), first_seen_at=NOW)
    new = add_article(db, provider, published_at=NOW, first_seen_at=NOW)
    # No publish date: sorted after the dated ones, newest first_seen_at first.
    undated_new = add_article(db, provider, published_at=None, first_seen_at=NOW)
    undated_old = add_article(db, provider, published_at=None, first_seen_at=NOW - timedelta(days=1))

    assert [a.id for a in repo.list()] == [new.id, old.id, undated_new.id, undated_old.id]


def test_list_pages_with_limit_and_offset(db, repo, provider):
    ids = [add_article(db, provider, published_at=NOW - timedelta(hours=i)).id for i in range(5)]

    assert [a.id for a in repo.list(limit=2)] == ids[:2]
    assert [a.id for a in repo.list(limit=2, offset=2)] == ids[2:4]
    assert repo.list(offset=10) == []


def test_random_articles_need_a_title_and_a_description(db, repo, provider):
    good = add_article(db, provider)
    add_article(db, provider, title="   ")
    add_article(db, provider, description="  ")
    add_article(db, provider, description=None)

    assert [a.id for a in repo.list_random(limit=10)] == [good.id]


def test_random_articles_respect_the_limit(db, repo, provider):
    for _ in range(6):
        add_article(db, provider)

    assert len(repo.list_random(limit=4)) == 4


def test_unscraped_articles_come_oldest_first(db, repo, provider):
    newer = add_article(db, provider, first_seen_at=NOW)
    older = add_article(db, provider, first_seen_at=NOW - timedelta(hours=3))
    add_article(db, provider, is_scraped=True, first_seen_at=NOW - timedelta(days=1))

    assert [a.id for a in repo.list_unscraped()] == [older.id, newer.id]
    assert [a.id for a in repo.list_unscraped(limit=1)] == [older.id]


# ---- updating ----------------------------------------------------------------------


def test_update_saves_the_changed_fields(db, repo, provider):
    article = repo.get(add_article(db, provider).id)

    repo.update(article, content="Full text", is_scraped=True)
    db.commit()
    db.expire_all()

    stored = repo.get(article.id)
    assert (stored.content, stored.is_scraped) == ("Full text", True)
    assert stored.title == article.title  # untouched fields stay


def test_updating_an_article_that_does_not_exist_fails(db, repo, provider):
    article = repo.get(add_article(db, provider).id)
    ghost = replace(article, id=uuid.uuid4())

    with pytest.raises(ValueError):
        repo.update(ghost, title="Nope")


# ---- hourly cleanup ----------------------------------------------------------------


def test_cleanup_deletes_old_articles_that_no_story_uses(db, repo, provider):
    cutoff = NOW - timedelta(days=30)
    add_article(db, provider, last_seen_at=cutoff - timedelta(days=1))
    recent_id = add_article(db, provider, last_seen_at=NOW).id

    deleted = repo.delete_unlinked_older_than(cutoff)

    assert deleted == 1
    assert stored_article_ids(db) == {recent_id}


def test_cleanup_keeps_old_articles_that_a_story_still_uses(db, repo, provider):
    cutoff = NOW - timedelta(days=30)
    linked = add_article(db, provider, last_seen_at=cutoff - timedelta(days=5))
    story = Story(title="Still live")
    db.add(story)
    db.flush()
    db.add(StoryArticle(story_id=story.id, article_id=linked.id))
    db.commit()

    deleted = repo.delete_unlinked_older_than(cutoff)

    assert deleted == 0
    assert stored_article_ids(db) == {linked.id}


def test_cleanup_keeps_an_article_seen_exactly_at_the_cutoff(db, repo, provider):
    cutoff = NOW - timedelta(days=30)
    edge = add_article(db, provider, last_seen_at=cutoff)

    assert repo.delete_unlinked_older_than(cutoff) == 0
    assert stored_article_ids(db) == {edge.id}


def test_cleanup_keeps_engagement_events_but_unlinks_them(db, repo, provider):
    cutoff = NOW - timedelta(days=30)
    old = add_article(db, provider, last_seen_at=cutoff - timedelta(days=1))
    event = EngagementEvent(
        session_id=uuid.uuid4(), article_id=old.id, event_type="read_complete",
        occurred_at=NOW, ingested_at=NOW,
    )
    db.add(event)
    db.commit()

    repo.delete_unlinked_older_than(cutoff)
    db.commit()
    db.expire_all()

    kept = db.get(EngagementEvent, event.id)
    assert kept is not None
    assert kept.article_id is None
    assert kept.occurred_at == NOW
