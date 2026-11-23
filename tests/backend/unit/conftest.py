"""Settings for every unit test: unit tests never use real configuration."""

import pytest

from Backend.config import get_settings


@pytest.fixture(autouse=True)
def fake_settings(monkeypatch):
    # Environment variables win over Backend/.env, so a developer's own .env
    # or the CI secrets can't change what the unit tests see.
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.test")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "test-publishable-key")
    # get_settings() is cached, so clear it before and after each test.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
