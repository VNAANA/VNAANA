"""Setup for the security tests: fake settings and services, no database.

These tests send real HTTP requests through the whole FastAPI app
(middleware, auth, routing), but every service behind it is a Mock, so
nothing reaches a database, Supabase, Ollama or Google.
"""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from Backend.config import get_settings
from Backend.main import app
from Backend.Presentation.dependencies import (
    get_ai_service,
    get_article_service,
    get_story_service,
    get_tag_service,
)


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    # Same idea as tests/backend/unit/conftest.py: a developer's own .env can't
    # make these tests talk to the real Supabase.
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def services():
    tags = Mock()
    tags.list_tags.return_value = []
    articles = Mock()
    articles.list_random_articles.return_value = []
    stories = Mock()
    ai = Mock()
    return SimpleNamespace(tags=tags, articles=articles, stories=stories, ai=ai)


@pytest.fixture
def client(services):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_tag_service] = lambda: services.tags
    app.dependency_overrides[get_article_service] = lambda: services.articles
    app.dependency_overrides[get_story_service] = lambda: services.stories
    app.dependency_overrides[get_ai_service] = lambda: services.ai
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
