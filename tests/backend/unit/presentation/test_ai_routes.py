"""HTTP contract checks without a live Ollama server."""

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.ai_service import AIService
from Backend.Logic.fontys_client import FontysClient
from Backend.Logic.ollama_client import OllamaClient
from Backend.Presentation import dependencies
from Backend.Presentation.dependencies import get_ai_service
from Backend.Presentation.routers.ai import router
from Backend.config import Settings


def test_ai_dependency_defaults_to_ollama(monkeypatch):
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)
    service = get_ai_service()
    assert settings.ai_provider == "ollama"
    assert isinstance(service.generate.__self__, OllamaClient)


@pytest.mark.parametrize("path", ["/ai/ask", "/ai/summarize"])
def test_article_routes_with_fontys_selected(monkeypatch, path):
    key = "offline-route-key"
    monkeypatch.setenv("AI_PROVIDER", "fontys")
    monkeypatch.setenv("FONTYS_API_KEY", key)
    settings = Settings(_env_file=None)
    assert key not in repr(settings)
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    def respond(request):
        assert request.headers["x-portkey-api-key"] == key
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({
            "status": "answered", "text": "It opened on Monday.",
            "evidence": "The library opened on Monday.",
        })}}]})

    app = FastAPI()
    app.include_router(router)
    body = {"article_text": "The library opened on Monday.", "language": "en"}
    if path == "/ai/ask":
        body["question"] = "When did the library open?"
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        monkeypatch.setattr(dependencies, "FontysClient", lambda **kwargs: FontysClient(**kwargs, http_client=http))
        with TestClient(app) as client:
            response = client.post(path, json=body)

    assert response.status_code == 200
    assert response.json()["text"] == "It opened on Monday."
    assert response.json()["status"] == "answered"
    assert key not in response.text


def test_unsupported_question_returns_http_200_with_insufficient_information():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_ai_service] = lambda: AIService(
        lambda _system, _prompt: json.dumps(
            {"status": "insufficient_information", "text": "", "evidence": ""}
        )
    )
    with TestClient(app) as client:
        result = client.post("/ai/ask", json={
            "article_text": "The bridge reopened today.", "question": "Who built it?", "language": "en",
        })
    response = result.json()
    assert result.status_code == 200
    assert response["status"] == "insufficient_information"
    assert response["sources"] == []
    assert "cannot answer" in response["text"]
