"""Which endpoints can change data without signing in.

Every write endpoint (POST, PUT, PATCH, DELETE) is checked by sending it a
request without a token. The list comes from the app itself (its OpenAPI
schema), so a NEW write endpoint is checked automatically: if someone adds
one without login, test_write_endpoint_needs_login fails for it.

Some endpoints are open on purpose (PUBLIC_ON_PURPOSE). Others are open for
now and will be locked down later (NOT_LOCKED_YET): their tests are skipped
with that reason until then. When you lock one down, remove it from
NOT_LOCKED_YET so its test runs.
"""

import uuid

import pytest

from Backend.main import app

WRITE_METHODS = {"post", "put", "patch", "delete"}

PUBLIC_ON_PURPOSE = {
    ("POST", "/auth/login"),    # signing in can't require being signed in
    ("POST", "/ai/ask"),        # Nova works for signed-out users too
    ("POST", "/ai/summarize"),
    ("POST", "/ai/stories/{story_id}/ask"),  # story Nova; the frontend sends no token
}

NOT_LOCKED_YET = {
    ("POST", "/stories"),
    ("PATCH", "/stories/{story_id}"),
    ("PUT", "/stories/{story_id}/tags"),
    ("POST", "/stories/{story_id}/articles"),
    ("DELETE", "/stories/{story_id}/articles/{article_id}"),
    ("POST", "/articles"),
}


def write_endpoints() -> list[tuple[str, str]]:
    return sorted(
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in WRITE_METHODS
    )


def with_ids(path: str) -> str:
    """Fill every {something_id} in the path with a random UUID."""
    for part in path.split("/"):
        if part.startswith("{") and part.endswith("}"):
            path = path.replace(part, str(uuid.uuid4()))
    return path


def cases() -> list:
    params = []
    for method, path in write_endpoints():
        if (method, path) in PUBLIC_ON_PURPOSE:
            continue
        marks = []
        if (method, path) in NOT_LOCKED_YET:
            marks.append(pytest.mark.skip(reason="Open for now; will be locked down later"))
        params.append(pytest.param(method, path, id=f"{method} {path}", marks=marks))
    return params


@pytest.mark.parametrize("method, path", cases())
def test_write_endpoint_needs_login(client, services, method, path):
    # An empty body on purpose: the login check runs before the body is read,
    # so a protected endpoint answers 401, while an open one tries to read
    # the body and answers 422 (or worse, does what was asked).
    response = client.request(method, with_ids(path), json={})

    assert response.status_code == 401, (
        f"{method} {path} answered {response.status_code} without a token. "
        "Add a login dependency, or (if it's meant to be open) add it to PUBLIC_ON_PURPOSE."
    )
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert not services.stories.mock_calls
    assert not services.articles.mock_calls


def test_the_exception_lists_only_contain_real_endpoints():
    # Keeps the lists honest: a renamed or removed endpoint must be taken off.
    existing = set(write_endpoints())

    assert PUBLIC_ON_PURPOSE <= existing
    assert NOT_LOCKED_YET <= existing


def test_an_endpoint_is_never_both_public_and_waiting_to_be_locked():
    assert not PUBLIC_ON_PURPOSE & NOT_LOCKED_YET
