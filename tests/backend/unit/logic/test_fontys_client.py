import json

import httpx
import pytest
from pydantic import SecretStr

from Backend.Logic.ai_service import AIModelError
from Backend.Logic.fontys_client import FontysClient


ENDPOINT = "https://api.portkey.ai/v1/chat/completions"
MODEL = "fontys-gpt-5.6-sol"
KEY = "offline-test-key"


def test_fontys_request_payload():
    def respond(request):
        assert str(request.url) == ENDPOINT
        assert request.headers["x-portkey-api-key"] == KEY
        assert "authorization" not in request.headers
        assert request.extensions["timeout"]["read"] == 12
        assert json.loads(request.content) == {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "instructions"},
                {"role": "user", "content": "article text"},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 4096,
            "stream": False,
        }
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"text":"answer"}'}, "finish_reason": "stop"}],
        })

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = FontysClient(SecretStr(KEY), MODEL, ENDPOINT, timeout_seconds=12, http_client=http)
        assert client.generate("instructions", "article text") == '{"text":"answer"}'


@pytest.mark.parametrize(("key", "endpoint"), [
    (None, ENDPOINT),
    (SecretStr(" "), ENDPOINT),
    (SecretStr(KEY), "http://api.portkey.ai/v1/chat/completions"),
])
def test_invalid_configuration_sends_no_request(key, endpoint):
    def unexpected(request):
        pytest.fail("Invalid configuration sent a request")

    with httpx.Client(transport=httpx.MockTransport(unexpected)) as http:
        with pytest.raises(AIModelError, match="not configured"):
            FontysClient(key, MODEL, endpoint, http_client=http).generate("system", "article")


@pytest.mark.parametrize("response", [
    httpx.Response(429, text=KEY),
    httpx.Response(307, headers={"location": "https://other.example/"}),
    httpx.Response(200, text="not JSON"),
    httpx.Response(200, json={"choices": []}),
    httpx.Response(200, json={"choices": [{"message": {"content": None}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": KEY}}]}),
    httpx.Response(200, json={"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]}),
])
def test_bad_responses_are_safe_and_not_retried(response):
    requests = []

    def respond(request):
        requests.append(request)
        return response

    with httpx.Client(transport=httpx.MockTransport(respond), follow_redirects=True) as http:
        client = FontysClient(SecretStr(KEY), MODEL, ENDPOINT, http_client=http)
        with pytest.raises(AIModelError) as exc:
            client.generate("system", "article")
    assert KEY not in str(exc.value)
    assert len(requests) == 1


def test_timeout_does_not_expose_upstream_error():
    def timeout(request):
        raise httpx.ReadTimeout(KEY, request=request)

    with httpx.Client(transport=httpx.MockTransport(timeout)) as http:
        client = FontysClient(SecretStr(KEY), MODEL, ENDPOINT, http_client=http)
        with pytest.raises(AIModelError, match="^Fontys is unavailable$"):
            client.generate("system", "article")
