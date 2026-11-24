import httpx

from Backend.Logic.ai_service import AIModelError

GROQ_SUMMARY_MODEL = "openai/gpt-oss-120b"
GROQ_SUMMARY_OPTIONS = {
    "reasoning_effort": "low",
    "include_reasoning": False,
    "max_completion_tokens": 512,
}


class GroqClient:
    def __init__(self, api_key: str, timeout_seconds: int = 90):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def generate_story_summary(self, prompt: str) -> dict:
        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": GROQ_SUMMARY_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    **GROQ_SUMMARY_OPTIONS,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            result = response.json()
            choice = result["choices"][0]
            usage = result.get("usage") or {}
            return {
                "text": choice["message"]["content"],
                "finish_reason": choice.get("finish_reason"),
                "reported_model": result.get("model"),
                "usage": {
                    "input_tokens": usage.get("prompt_tokens"),
                    "output_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
            }
        except httpx.HTTPStatusError as exc:
            raise AIModelError(
                f"Groq request failed (HTTP {exc.response.status_code})"
            ) from None
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
            AttributeError,
        ):
            raise AIModelError(
                "Groq is unavailable or returned an invalid response"
            ) from None
