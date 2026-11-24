"""ArticleRepository translation cache on the real migrated Postgres database
(setup in ../conftest.py), plus the batch lookup of story translations."""

import uuid

import pytest
from sqlalchemy import func, select

from Backend.Dal.models import (
    Article as ArticleModel,
    ArticleTranslation,
    Provider,
    Story,
)
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository


@pytest.fixture
def article(db) -> ArticleModel:
    provider = Provider(name="NOS", domain="nos.nl", country_code="NL", reliability_status="verified")
    db.add(provider)
    db.flush()
    article = ArticleModel(
        provider_id=provider.id,
        canonical_url=f"https://nos.nl/{uuid.uuid4()}",
        title="Titel",
        description="Beschrijving",
    )
    db.add(article)
    db.commit()
    return article


def test_no_translations_yet(db, article):
    assert ArticleRepository(db).get_translations([article.id], "en") == {}


def test_an_empty_id_list_does_not_query(db):
    assert ArticleRepository(db).get_translations([], "en") == {}


def test_saved_translation_can_be_read_back(db, article):
    repo = ArticleRepository(db)

    saved = repo.save_translation(
        article.id, "en", source_description="Beschrijving", description="Description"
    )
    db.commit()
    loaded = repo.get_translations([article.id, uuid.uuid4()], "en")

    assert loaded == {article.id: saved}
    assert (saved.source_description, saved.description) == ("Beschrijving", "Description")
    assert saved.updated_at is not None
    assert repo.get_translations([article.id], "de") == {}


def test_saving_again_overwrites_the_same_row(db, article):
    repo = ArticleRepository(db)
    repo.save_translation(article.id, "en", source_description="Oud", description="Old")
    db.commit()

    updated = repo.save_translation(article.id, "en", source_description="Nieuw", description="New")
    db.commit()

    assert (updated.source_description, updated.description) == ("Nieuw", "New")
    assert repo.get_translations([article.id], "en")[article.id].description == "New"
    assert db.scalar(select(func.count()).select_from(ArticleTranslation)) == 1


def test_deleting_the_article_deletes_its_translations(db, article):
    ArticleRepository(db).save_translation(
        article.id, "en", source_description="Beschrijving", description="Description"
    )
    db.commit()

    db.delete(article)
    db.commit()

    assert db.scalar(select(func.count()).select_from(ArticleTranslation)) == 0


def test_story_translations_are_fetched_for_a_whole_page(db):
    repo = StoryRepository(db)
    translated, untranslated = Story(title="Een"), Story(title="Twee")
    db.add_all([translated, untranslated])
    db.commit()
    saved = repo.save_translation(translated.id, "en", title="One", summary=None, context=None)
    repo.save_translation(translated.id, "de", title="Eins", summary=None, context=None)
    db.commit()

    assert repo.get_translations([translated.id, untranslated.id], "en") == {translated.id: saved}
    assert repo.get_translations([], "en") == {}
