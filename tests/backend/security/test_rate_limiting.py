"""Rate limiting: 60 requests per minute per client IP, for the whole API.

The limit itself lives in Backend/Presentation/rate_limit.py. The tests read
it from the settings instead of hard-coding 60, so they keep working with a
different RATE_LIMIT (only test_the_limit_is_sixty_a_minute checks the number).
"""

import time

import pytest

from limits import parse

from Backend.config import get_settings

LIMIT = parse(get_settings().rate_limit)  # "60 per 1 minute"
MAX_REQUESTS = LIMIT.amount
FRONTEND = "http://localhost:5173"


def use_up_the_limit(client, path="/tags", **headers):
    for _ in range(MAX_REQUESTS):
        assert client.get(path, headers=headers).status_code == 200


def test_the_limit_is_sixty_a_minute():
    assert (LIMIT.amount, LIMIT.get_expiry()) == (60, 60)


def test_requests_up_to_the_limit_are_allowed(client):
    use_up_the_limit(client)


def test_the_request_after_the_limit_gets_a_429(client):
    use_up_the_limit(client)

    response = client.get("/tags")

    assert response.status_code == 429
    assert response.json() == {"detail": "Too many requests. Please wait a moment and try again."}


def test_a_429_says_how_long_to_wait(client):
    use_up_the_limit(client)

    response = client.get("/tags")

    assert 0 < int(response.headers["Retry-After"]) <= 60
    assert response.headers["X-RateLimit-Remaining"] == "0"


def test_the_limit_is_shared_by_every_endpoint(client):
    half = MAX_REQUESTS // 2
    for _ in range(half):
        assert client.get("/tags").status_code == 200
    for _ in range(MAX_REQUESTS - half):
        assert client.get("/articles/random").status_code == 200

    assert client.get("/tags").status_code == 429


@pytest.mark.parametrize("method, path, body", [
    ("POST", "/auth/login", {"email": "a@b.test", "password": "secret"}),
    ("POST", "/ai/ask", {"article_text": "Text", "question": "Why?"}),
    ("POST", "/ai/summarize", {"article_text": "Text"}),
    ("POST", "/stories", {"title": "Spam"}),
    ("GET", "/auth/me", None),
])
def test_blocked_requests_never_reach_the_endpoint(client, services, method, path, body):
    use_up_the_limit(client)

    response = client.request(method, path, json=body)

    assert response.status_code == 429
    # Nothing ran behind the limiter: no Ollama call, no story created.
    assert not services.ai.mock_calls
    assert not services.stories.mock_calls


def test_every_ip_has_its_own_limit(client):
    use_up_the_limit(client, **{"X-Forwarded-For": "203.0.113.1"})

    assert client.get("/tags", headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert client.get("/tags", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 200


def test_a_made_up_ip_in_front_of_the_real_one_does_not_help(client):
    # Azure appends the real client IP at the end of X-Forwarded-For. A client
    # that puts a new fake IP in front every time is still the same client.
    for i in range(MAX_REQUESTS):
        fake = {"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.1"}
        assert client.get("/tags", headers=fake).status_code == 200

    blocked = client.get("/tags", headers={"X-Forwarded-For": "10.9.9.9, 203.0.113.1"})

    assert blocked.status_code == 429


def test_the_limit_resets_after_a_minute(client, monkeypatch):
    now = [time.time()]
    monkeypatch.setattr(time, "time", lambda: now[0])
    use_up_the_limit(client)
    assert client.get("/tags").status_code == 429

    now[0] += 61

    assert client.get("/tags").status_code == 200


def test_cors_preflight_requests_do_not_count(client):
    preflight = {"Origin": FRONTEND, "Access-Control-Request-Method": "GET"}
    for _ in range(MAX_REQUESTS * 2):
        assert client.options("/tags", headers=preflight).status_code == 200

    assert client.get("/tags").status_code == 200


def test_the_frontend_can_read_a_429(client):
    # Without the CORS header the browser hides the response, and the
    # frontend can't tell "too many requests" apart from "server down".
    use_up_the_limit(client)

    response = client.get("/tags", headers={"Origin": FRONTEND})

    assert response.status_code == 429
    assert response.headers["Access-Control-Allow-Origin"] == FRONTEND
