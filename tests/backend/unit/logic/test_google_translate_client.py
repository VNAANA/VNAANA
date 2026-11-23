"""GoogleTranslateClient against a fake HTTP transport. Never calls Google."""

import json

import httpx
import pytest

from Backend.Logic.exceptions import TranslationUnavailableError
from Backend.Logic.google_translate_client import TRANSLATE_URL, GoogleTranslateClient


def client_returning(status=200, body=None, requests=None, error=None):
    def handler(request):
        if requests is not None:
            requests.append(request)
        if error is not None:
            raise error
        return httpx.Response(status, json=body)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return GoogleTranslateClient(api_key="test-key", http_client=http)


def translations(*texts):
    return {"data": {"translations": [{"translatedText": text} for text in texts]}}


def test_sends_all_texts_in_one_request_with_the_key_in_a_header():
    requests = []
    client = client_returning(body=translations("Title", "Context"), requests=requests)

    result = client.translate(["Titel", "Context"], source="nl", target="en")

    assert result == ["Title", "Context"]
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == TRANSLATE_URL
    assert request.headers["X-goog-api-key"] == "test-key"
    # The key goes in the header, never in the URL where it would end up in logs.
    assert "key=" not in str(request.url)
    assert json.loads(request.content) == {
        "q": ["Titel", "Context"], "source": "nl", "target": "en", "format": "text",
    }


def test_html_entities_are_decoded():
    client = client_returning(body=translations("It&#39;s &quot;news&quot; &amp; more"))

    assert client.translate(["x"], source="nl", target="en") == ['It\'s "news" & more']


def test_nothing_to_translate_makes_no_request():
    requests = []
    client = client_returning(requests=requests)

    assert client.translate([], source="nl", target="en") == []
    assert requests == []


@pytest.mark.parametrize("key", [None, "", "   "])
def test_missing_key_fails_before_calling_google(key):
    client = GoogleTranslateClient(api_key=key)

    with pytest.raises(TranslationUnavailableError, match="not configured"):
        client.translate(["Titel"], source="nl", target="en")


@pytest.mark.parametrize("status", [403, 429])
def test_quota_errors(status):
    client = client_returning(status=status, body={"error": {}})

    with pytest.raises(TranslationUnavailableError, match="quota"):
        client.translate(["Titel"], source="nl", target="en")


def test_other_http_errors_do_not_leak_the_text():
    client = client_returning(status=400, body={"error": {"message": "bad"}})

    with pytest.raises(TranslationUnavailableError) as raised:
        client.translate(["Geheime artikeltekst"], source="nl", target="en")

    assert "Geheime" not in str(raised.value)


def test_network_error():
    client = client_returning(error=httpx.ConnectTimeout("timeout"))

    with pytest.raises(TranslationUnavailableError, match="unavailable"):
        client.translate(["Titel"], source="nl", target="en")


@pytest.mark.parametrize("body", [
    {"unexpected": True},
    {"data": {"translations": [{"wrong": "x"}]}},
    translations("only one"),
])
def test_invalid_or_incomplete_responses(body):
    client = client_returning(body=body)

    with pytest.raises(TranslationUnavailableError, match="invalid"):
        client.translate(["Titel", "Context"], source="nl", target="en")
