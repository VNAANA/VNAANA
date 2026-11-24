"""ProviderRepository on an in-memory SQLite database (setup in ../conftest.py)."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from Backend.Dal.repositories.provider_repository import ProviderRepository


@pytest.fixture
def repo(db) -> ProviderRepository:
    return ProviderRepository(db)


def add_provider(repo, name="NOS", domain="nos.nl", **fields):
    return repo.add(name=name, domain=domain, reliability_status="verified", **fields)


def test_an_added_provider_comes_back_with_its_fields(db, repo):
    provider = add_provider(repo, country_code="NL")
    db.commit()

    assert provider.id is not None
    assert (provider.name, provider.domain, provider.country_code) == ("NOS", "nos.nl", "NL")
    assert provider.reliability_status == "verified"


def test_the_database_fills_in_created_at(db, repo):
    provider = add_provider(repo)
    db.commit()

    assert provider.created_at is not None


def test_a_provider_can_be_found_by_id(db, repo):
    provider = add_provider(repo)
    db.commit()
    db.expire_all()

    assert repo.get(provider.id) == provider
    assert repo.get(uuid.uuid4()) is None


def test_a_provider_can_be_found_by_domain(db, repo):
    nos = add_provider(repo)
    db.commit()

    assert repo.get_by_domain("nos.nl") == nos
    assert repo.get_by_domain("bbc.co.uk") is None


def test_domains_are_unique(db, repo):
    add_provider(repo)
    db.commit()

    with pytest.raises(IntegrityError):
        add_provider(repo, name="NOS again")


def test_all_providers_are_listed_by_name(db, repo):
    add_provider(repo, "NOS", "nos.nl")
    add_provider(repo, "BBC", "bbc.co.uk")
    add_provider(repo, "Reuters", "reuters.com")
    db.commit()

    assert [provider.name for provider in repo.list_all()] == ["BBC", "NOS", "Reuters"]
