import math

import httpx
from pydantic import SecretStr

from Backend.Logic.ai_service import AIModelError


class FontysClient:
    def __init__(
        self,
        api_key: SecretStr | None,
        model: str,
        endpoint: str,
        timeout_seconds: float = 90,
        http_client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.model = model.strip()
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.http_client = http_client

    def generate(self, system: str, prompt: str) -> str:
        key = self.api_key.get_secret_value().strip() if self.api_key else ""
        try:
            url = httpx.URL(self.endpoint)
        except httpx.InvalidURL:
            raise AIModelError("Fontys is not configured correctly") from None
        if (
            not key
            or not self.model
            or url.scheme != "https"
            or not url.host
            or url.userinfo
            or url.query
            or url.fragment
            or not math.isfinite(self.timeout_seconds)
            or self.timeout_seconds <= 0
        ):
            raise AIModelError("Fontys is not configured correctly")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 4096,
            "stream": False,
        }
        try:
            if self.http_client is None:
                with httpx.Client() as client:
                    response = self._post(client, url, key, payload)
            else:
                response = self._post(self.http_client, url, key, payload)
        except (httpx.RequestError, httpx.InvalidURL, ValueError):
            raise AIModelError("Fontys is unavailable") from None

        if response.status_code != 200:
            raise AIModelError(
                f"Fontys refused the request (HTTP {response.status_code})"
            )
        try:
            choice = response.json()["choices"][0]
            text = choice["message"]["content"]
        except (ValueError, KeyError, TypeError, IndexError):
            raise AIModelError("Fontys returned an invalid response") from None
        if (
            choice.get("finish_reason") not in (None, "stop")
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise AIModelError("Fontys returned no complete generated text")
        if key in text:
            raise AIModelError("Fontys returned an invalid response")
        return text

    def _post(
        self, client: httpx.Client, url: httpx.URL, key: str, payload: dict
    ) -> httpx.Response:
        return client.post(
            url,
            json=payload,
            headers={"x-portkey-api-key": key},
            timeout=self.timeout_seconds,
            follow_redirects=False,
        )
