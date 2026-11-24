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


def echo_client(requests):
    """Answers every request with its own texts prefixed by EN:, like Google would."""

    def handler(request):
        texts = json.loads(request.content)["q"]
        requests.append(texts)
        return httpx.Response(200, json=translations(*[f"EN:{text}" for text in texts]))

    return GoogleTranslateClient(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_more_than_128_texts_are_split_over_requests_in_order():
    requests = []
    texts = [f"Tekst {i}" for i in range(300)]

    result = echo_client(requests).translate(texts, source="nl", target="en")

    assert [len(chunk) for chunk in requests] == [128, 128, 44]
    assert result == [f"EN:Tekst {i}" for i in range(300)]


def test_large_texts_are_split_by_size():
    requests = []
    # Each text is 20 KB, so only two fit within the 50 KB budget per request.
    texts = [f"{i}" + "a" * 20_000 for i in range(5)]

    result = echo_client(requests).translate(texts, source="nl", target="en")

    assert [len(chunk) for chunk in requests] == [2, 2, 1]
    assert result == [f"EN:{text}" for text in texts]


def test_size_counts_bytes_not_characters():
    requests = []
    # "é" is 2 bytes in UTF-8: 3 × 10 000 é = 60 KB, so they can't share one request.
    texts = ["é" * 10_000] * 3

    echo_client(requests).translate(texts, source="nl", target="en")

    assert [len(chunk) for chunk in requests] == [2, 1]


def test_one_text_over_the_budget_still_gets_its_own_request():
    requests = []

    result = echo_client(requests).translate(["a" * 60_000, "b"], source="nl", target="en")

    assert [len(chunk) for chunk in requests] == [1, 1]
    assert result == ["EN:" + "a" * 60_000, "EN:b"]


def test_a_failing_chunk_fails_the_whole_translation():
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) == 2:
            return httpx.Response(429, json={"error": {}})
        texts = json.loads(request.content)["q"]
        return httpx.Response(200, json=translations(*texts))

    client = GoogleTranslateClient(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    with pytest.raises(TranslationUnavailableError, match="quota"):
        client.translate(["x"] * 200, source="nl", target="en")
