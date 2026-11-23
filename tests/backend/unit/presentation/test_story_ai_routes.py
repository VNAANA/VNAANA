import json
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.ai_service import AIService
from Backend.Logic.domain.article import Article, ArticleProvider
from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.domain.story_articles import StoryArticleDetails
from Backend.Logic.fontys_client import FontysClient
from Backend.Logic.ollama_client import OllamaClient
from Backend.Logic.story_service import StoryService
from Backend.Presentation import dependencies
from Backend.Presentation.error_handlers import register_error_handlers
from Backend.Presentation.routers.ai import router
from Backend.config import Settings


@pytest.fixture
def story_api():
    now = datetime.now(timezone.utc)
    links = []
    for name, content in (("First", "De bibliotheek opent binnenkort."),
                          ("Second", "De bibliotheek opent op zaterdag.")):
        provider = ArticleProvider(uuid4(), name, f"{name.lower()}.example", None, "verified")
        article = Article(
            id=uuid4(), provider_id=provider.id, provider=provider,
            canonical_url=f"https://{provider.domain}/library", title="Bibliotheek",
            description=None, content=content, is_scraped=True, author=None,
            language="nl", published_at=now, first_seen_at=now, last_seen_at=now,
        )
        links.append(StoryArticleDetails(article, None, name == "First", now))
    story = StoryDetails(uuid4(), "Bibliotheek", None, "Unused context", StoryStatus.published,
                         now, now, articles=links)
    repository = Mock()
    repository.get.return_value = story
    generate = Mock()
    app = FastAPI()
    register_error_handlers(app)
    app.include_router(router)
    app.dependency_overrides[dependencies.get_story_service] = lambda: StoryService(repository, Mock(), Mock())
    app.dependency_overrides[dependencies.get_ai_service] = lambda: AIService(generate)
    with TestClient(app) as client:
        yield client, app, story, repository, generate


def ask(client, story, language="nl", **fields):
    return client.post(f"/ai/stories/{story.id}/ask", json={
        "question": "Wanneer opent de bibliotheek?", "language": language, **fields,
    })


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_unpublished_story(story_api, missing):
    client, _, story, repository, generate = story_api
    if missing:
        repository.get.return_value = None
    else:
        story.status = StoryStatus.draft
    assert ask(client, story).status_code == 404
    repository.get.assert_called_once_with(story.id)
    generate.assert_not_called()


@pytest.mark.parametrize("article_count", [1, 2])
def test_answer_uses_linked_article(story_api, article_count):
    client, _, story, _, generate = story_api
    story.articles = story.articles[-article_count:]
    story.articles[0].is_primary = True
    article = story.articles[-1].article
    generate.return_value = json.dumps({
        "status": "answered", "text": "De bibliotheek opent op zaterdag.",
        "evidence": [{"article_id": str(article.id), "quote": article.content}],
        "sources": ["https://invented.example"],
    })
    response = ask(client, story)
    assert response.status_code == 200
    answer = response.json()
    assert answer["status"] == "answered"
    assert answer["text"] == "De bibliotheek opent op zaterdag."
    assert answer["sources"] == [article.canonical_url]
    assert f"{article_count} van de {article_count}" in answer["uncertainty"]
    prompt = json.loads(generate.call_args.args[1])
    assert "history" not in prompt
    assert [item["article_id"] for item in prompt["articles"]] == [
        str(link.article.id) for link in story.articles
    ]
    assert prompt["articles"][-1]["publisher"] == "Second"
    assert prompt["articles"][-1]["published_at"] == article.published_at.isoformat()
    assert "Unused context" not in generate.call_args.args[1]


def test_empty_history_preserves_the_single_question_prompt(story_api):
    client, _, story, _, generate = story_api
    generate.return_value = json.dumps({"status": "insufficient_information"})
    assert ask(client, story).status_code == 200
    original = generate.call_args
    assert ask(client, story, history=[]).status_code == 200
    assert generate.call_args == original


def test_follow_up_keeps_history_separate_from_article_evidence(story_api):
    client, _, story, _, generate = story_api
    article = story.articles[1].article
    history = [
        {"role": "user", "content": "Wat gebeurt er in het dorp?"},
        {"role": "assistant", "content": "Er opent een bibliotheek."},
    ]
    generate.return_value = json.dumps({
        "status": "answered", "text": "De bibliotheek opent op zaterdag.",
        "evidence": [{"article_id": str(article.id), "quote": article.content}],
    })
    response = ask(client, story, question="Wanneer gebeurt dat?", history=history)
    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["sources"] == [article.canonical_url]
    system, payload = generate.call_args.args
    prompt = json.loads(payload)
    assert prompt["question"] == "Wanneer gebeurt dat?"
    assert prompt["history"] == history
    assert prompt["articles"][1]["body"] == article.content
    assert "untrusted context" in system


@pytest.mark.parametrize(("messages", "error"), [
    ([("system", "Instruction"), ("assistant", "Answer")], "role"),
    ([("assistant", "Answer"), ("user", "Question")], "completed"),
    ([("user", "Question")], "completed"),
    ([("user", "Question"), ("assistant", "Answer")] * 3, "at most 4"),
    ([("user", " "), ("assistant", "Answer")], "blank"),
    ([("user", "x" * 501), ("assistant", "Answer")], "at most 500"),
    ([("user", "é" * 500), ("assistant", "é" * 500)], "2,000 UTF-8 bytes"),
])
def test_invalid_history_is_rejected_before_inference(story_api, messages, error):
    client, _, story, _, generate = story_api
    response = ask(client, story, history=[
        {"role": role, "content": content} for role, content in messages
    ])
    assert response.status_code == 422
    assert error in response.text
    generate.assert_not_called()


def test_prior_answer_cannot_be_used_as_article_evidence(story_api):
    client, _, story, _, generate = story_api
    unsupported = "De bibliotheek opent om negen uur."
    generate.return_value = json.dumps({
        "status": "answered", "text": unsupported,
        "evidence": [{"article_id": str(story.articles[1].article.id), "quote": unsupported}],
    })
    response = ask(client, story, question="Hoe laat is dat?", history=[
        {"role": "user", "content": "Hoe laat gaat de bibliotheek open?"},
        {"role": "assistant", "content": unsupported},
    ])
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_information"
    assert response.json()["sources"] == []


def test_missing_body_is_disclosed(story_api):
    client, _, story, _, generate = story_api
    story.articles[0].article.content = ""
    article = story.articles[1].article
    generate.return_value = json.dumps({
        "status": "answered", "text": "De bibliotheek opent op zaterdag.",
        "evidence": [{"article_id": str(article.id), "quote": article.content}],
    })
    response = ask(client, story)
    assert response.status_code == 200
    assert "1 van de 2" in response.json()["uncertainty"]
    assert len(json.loads(generate.call_args.args[1])["articles"]) == 1


def test_conflicting_accounts_use_both_sources(story_api):
    client, _, story, _, generate = story_api
    first, second = [link.article for link in story.articles]
    first.content = "De bibliotheek opent op zondag."
    generate.return_value = json.dumps({
        "status": "conflicting", "text": "First reports Sunday, while Second reports Saturday.",
        "evidence": [{"article_id": str(article.id), "quote": article.content} for article in (first, second)],
    })
    response = ask(client, story, "en")
    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["sources"] == [first.canonical_url, second.canonical_url]
    assert "The answer reports differing accounts from the cited Articles." in response.json()["uncertainty"]


@pytest.mark.parametrize("article_count", [1, 2])
def test_conflicting_answer_requires_two_distinct_articles(story_api, article_count):
    client, _, story, _, generate = story_api
    story.articles = story.articles[:article_count]
    article = story.articles[0].article
    citation = {"article_id": str(article.id), "quote": article.content}
    generate.return_value = json.dumps({
        "status": "conflicting", "text": "De bronnen geven verschillende openingsdagen.",
        "evidence": [citation, citation],
    })
    response = ask(client, story)
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_information"
    assert response.json()["sources"] == []
    assert "verschillende lezingen" not in response.json()["uncertainty"]


@pytest.mark.parametrize("unknown_id", [True, False])
def test_invalid_evidence_returns_insufficient_information(story_api, unknown_id):
    client, _, story, _, generate = story_api
    first, second = [link.article for link in story.articles]
    generate.return_value = json.dumps({
        "status": "answered", "text": "De bibliotheek opent op zaterdag.",
        "evidence": [{"article_id": str(uuid4() if unknown_id else first.id), "quote": second.content}],
    })
    response = ask(client, story)
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_information"
    assert response.json()["sources"] == []


def test_oversized_story_is_rejected_before_inference(story_api):
    client, _, story, _, generate = story_api
    story.articles[1].article.content = "é" * 7000
    response = ask(client, story)
    assert response.status_code == 422
    assert "without truncation" in response.json()["detail"]
    generate.assert_not_called()


@pytest.mark.parametrize("article_count", [1, 2])
def test_story_without_usable_bodies_skips_inference(story_api, article_count):
    client, _, story, _, generate = story_api
    story.articles = story.articles[:article_count]
    for link in story.articles:
        link.article.content = None
    response = ask(client, story)
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_information"
    assert response.json()["sources"] == []
    assert f"0 van de {article_count}" in response.json()["uncertainty"]
    generate.assert_not_called()


@pytest.mark.parametrize("provider", ["ollama", "fontys"])
def test_story_route_reuses_configured_provider(story_api, monkeypatch, provider):
    client, app, story, _, _ = story_api
    app.dependency_overrides.pop(dependencies.get_ai_service)
    settings = Settings(ai_provider=provider, fontys_api_key="offline-test-key", _env_file=None)
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    article = story.articles[1].article
    raw = json.dumps({
        "status": "answered", "text": "De bibliotheek opent op zaterdag.",
        "evidence": [{"article_id": str(article.id), "quote": article.content}],
    })

    def ollama_response(self, path, payload=None):
        if path == "/api/tags":
            return {"models": [{"name": self.model}]}
        assert path == "/api/generate"
        assert payload["truncate"] is payload["shift"] is False
        assert payload["options"]["num_ctx"] == 16_384
        return {"response": raw}

    def fontys_response(request):
        assert request.headers["x-portkey-api-key"] == "offline-test-key"
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        assert "truncate" not in payload
        return httpx.Response(200, json={"choices": [{"message": {"content": raw}}]})

    monkeypatch.setattr(OllamaClient, "_json_request", ollama_response)
    with httpx.Client(transport=httpx.MockTransport(fontys_response)) as http:
        monkeypatch.setattr(dependencies, "FontysClient", lambda **kwargs: FontysClient(**kwargs, http_client=http))
        response = ask(client, story)
    assert response.status_code == 200
    assert response.json()["status"] == "answered"
    assert response.json()["sources"] == [article.canonical_url]
