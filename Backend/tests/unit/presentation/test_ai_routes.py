"""HTTP contract checks without a live Ollama server or extra test packages."""

import asyncio
import json

from fastapi import FastAPI

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
    request_body = json.dumps(
        {"article_text": "The bridge reopened today.", "question": "Who built it?", "language": "en"}
    ).encode("utf-8")
    messages = []

    async def receive():
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/ai/ask",
        "raw_path": b"/ai/ask", "root_path": "", "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "server": ("testserver", 80), "client": ("testclient", 12345),
    }
    asyncio.run(app(scope, receive, send))

    start = next(message for message in messages if message["type"] == "http.response.start")
    body = b"".join(message["body"] for message in messages if message["type"] == "http.response.body")
    response = json.loads(body)
    assert start["status"] == 200
    assert response["status"] == "insufficient_information"
    assert response["sources"] == []
    assert "cannot answer" in response["text"]
