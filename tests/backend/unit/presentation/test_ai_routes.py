"""HTTP contract checks without a live Ollama server."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from Backend.Logic.ai_service import AIService
from Backend.Presentation.dependencies import get_ai_service
from Backend.Presentation.routers.ai import router


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
