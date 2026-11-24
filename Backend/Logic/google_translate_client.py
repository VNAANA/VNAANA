"""Google Cloud Translation Basic (v2) client.

The API key is only ever sent from the backend; it must never reach the
frontend. Every failure becomes a TranslationUnavailableError, and error
messages never contain the text that was being translated.
"""

import html

import httpx

from Backend.Logic.exceptions import TranslationUnavailableError

TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

# Google rejects a v2 request with more than 128 texts or over 100K bytes.
# A feed page can go past both, so bigger batches are split into several
# requests. The byte budget leaves room for the JSON around the texts.
MAX_TEXTS_PER_REQUEST = 128
MAX_TEXT_BYTES_PER_REQUEST = 50_000


class GoogleTranslateClient:
    def __init__(
        self,
        api_key: str | None,
        timeout_seconds: float = 15,
        http_client: httpx.Client | None = None,
    ):
        self.api_key = api_key.strip() if api_key else None
        self.timeout_seconds = timeout_seconds
        # Tests pass a client with a mock transport; normally a new one is made per call.
        self.http_client = http_client

    def translate(self, texts: list[str], *, source: str, target: str) -> list[str]:
        if not texts:
            return []

        if not self.api_key:
            raise TranslationUnavailableError("Translation is not configured")

        translated: list[str] = []
        for chunk in _chunks(texts):
            translated.extend(
                self._translate_chunk(chunk, source=source, target=target)
            )
        return translated

    def _translate_chunk(
        self, texts: list[str], *, source: str, target: str
    ) -> list[str]:
        try:
            response = self._post(
                {
                    # v2 accepts a list, so many texts go in one request.
                    "q": texts,
                    "source": source,
                    "target": target,
                    "format": "text",
                }
            )
        except httpx.HTTPError as exc:
            raise TranslationUnavailableError(
                "Translation service is unavailable"
            ) from exc

        # 403 is also what Google returns when the daily character quota is used up.
        if response.status_code in (403, 429):
            raise TranslationUnavailableError(
                "Translation quota exceeded, try again later"
            )

        if response.status_code != 200:
            raise TranslationUnavailableError(
                f"Translation service refused the request (HTTP {response.status_code})"
            )

        try:
            translations = response.json()["data"]["translations"]
            translated = [item["translatedText"] for item in translations]
        except (ValueError, KeyError, TypeError) as exc:
            raise TranslationUnavailableError(
                "Translation service returned an invalid response"
            ) from exc

        if len(translated) != len(texts) or not all(
            isinstance(text, str) for text in translated
        ):
            raise TranslationUnavailableError(
                "Translation service returned an invalid response"
            )

        # Google can return entities like &#39; even for plain text. The result
        # is still plain text after this; it must never be rendered as HTML.
        return [html.unescape(text) for text in translated]

    def _post(self, payload: dict) -> httpx.Response:
        headers = {"X-goog-api-key": self.api_key}

        if self.http_client is not None:
            return self.http_client.post(
                TRANSLATE_URL,
                json=payload,
                headers=headers,
                timeout=self.timeout_seconds,
            )

        with httpx.Client(timeout=self.timeout_seconds) as client:
            return client.post(TRANSLATE_URL, json=payload, headers=headers)


def _chunks(texts: list[str]) -> list[list[str]]:
    """Split texts into groups that each fit in one request, keeping their order.

    A single text bigger than the byte budget gets a request of its own; if
    Google rejects it, that fails like any other refused request.
    """
    chunks: list[list[str]] = []
    current: list[str] = []
    current_bytes = 0

    for text in texts:
        size = len(text.encode("utf-8"))
        full = len(current) == MAX_TEXTS_PER_REQUEST
        too_big = current and current_bytes + size > MAX_TEXT_BYTES_PER_REQUEST

        if full or too_big:
            chunks.append(current)
            current, current_bytes = [], 0

        current.append(text)
        current_bytes += size

    if current:
        chunks.append(current)

    return chunks
