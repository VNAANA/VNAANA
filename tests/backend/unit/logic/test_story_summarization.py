import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID

import httpx
import pytest

from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.domain.story_articles import StoryArticleDetails
from Backend.Logic.story_summarization_service import StorySummarizationService
from Backend.Logic.story_summary_prompts import (
    MULTI_ARTICLE_INSTRUCTION,
    SINGLE_ARTICLE_INSTRUCTION,
)
from Backend.config import Settings
from Backend.jobs import summarize_grouped_stories as job

WHEN = datetime(2026, 11, 10, 8, 13, 13, tzinfo=timezone.utc)


def linked_article(number, body="  Originele tekst.\n\nVolgende alinea.  "):
    article = SimpleNamespace(
        id=UUID(int=number),
        title=f"Artikel {number}",
        provider=SimpleNamespace(name="NOS"),
        published_at=WHEN,
        content=body,
    )
    return StoryArticleDetails(article, None, number == 2, WHEN)


def published_story(*links):
    return StoryDetails(
        UUID(int=9),
        "Het verhaal",
        None,
        "Primary context",
        StoryStatus.published,
        WHEN,
        WHEN,
        articles=list(links),
    )


@pytest.mark.parametrize(
    ("count", "instruction_hash", "version"),
    [
        (
            1,
            "c29f5320a095e48b6e29b9e63a996ce8eb390b6f2b4841540a200c1722cd03ef",
            "single_article_v1",
        ),
        (
            2,
            "566e71e7a5620c53835e360e5d3d53a60f2898a25bd5bba326fae3eb5bd840cb",
            "multiple_articles_v1",
        ),
    ],
)
def test_approved_prompt_and_order(count, instruction_hash, version):
    generate = Mock(return_value={"text": "Het nieuws.", "finish_reason": "stop"})
    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    story = published_story(*[linked_article(n) for n in range(count, 0, -1)])
    result = service.candidate(story)
    prompt = generate.call_args.args[0]
    instruction = SINGLE_ARTICLE_INSTRUCTION if count == 1 else MULTI_ARTICLE_INSTRUCTION
    assert hashlib.sha256(instruction.encode()).hexdigest() == instruction_hash
    expected = [instruction, "STORY TITLE: Het verhaal"]
    for n in range(1, count + 1):
        expected.append(
            f"ARTICLE {n}\nArticle ID: {UUID(int=n)}\nTitle: Artikel {n}\n"
            f"Publisher: NOS\nPublication time: {WHEN.isoformat()}\n"
            f"Primary Article: {'yes' if n == 2 else 'no'}\n"
            "Full body:\n  Originele tekst.\n\nVolgende alinea.  "
        )
    assert prompt == "\n\n".join(expected)
    assert result["prompt_version"] == version
    assert result["input_sha256"] == hashlib.sha256(prompt.encode()).hexdigest()
    assert all("body" not in source for source in result["articles"])


@pytest.mark.parametrize("body", [None, " \n\t "])
def test_any_missing_body_skips_whole_story(body):
    generate = Mock()
    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    result = service.candidate(
        published_story(linked_article(1), linked_article(2, body))
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "missing_article_body"
    generate.assert_not_called()


@pytest.mark.parametrize(
    ("text", "finish", "reason"),
    [
        (" ", "stop", "empty_output"),
        ("partial", "length", "incomplete_output"),
        ("x" * 2501, "stop", "summary_too_long"),
    ],
)
def test_output_validation(text, finish, reason):
    generate = Mock(return_value={"text": text, "finish_reason": finish})
    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    result = service.candidate(published_story(linked_article(1)))
    assert result["status"] == "failed" and result["reason"] == reason
    assert result["summary"] is None


def test_provider_settings_and_sanitized_groq_failure(monkeypatch):
    post = Mock(
        return_value=httpx.Response(
            429,
            request=httpx.Request("POST", "https://api.groq.com"),
            json={"error": "private response"},
        )
    )
    monkeypatch.setattr("Backend.Logic.groq_client.httpx.post", post)
    settings = Settings(_env_file=None, groq_api_key="fake-key")
    story = published_story(linked_article(1))
    result = job.build_service(settings, "groq").candidate(story)
    assert result["reason"] == "provider_error"
    assert result["error"] == "Groq request failed (HTTP 429)"
    assert post.call_count == 1
    request = post.call_args.kwargs["json"]
    assert request["model"] == "openai/gpt-oss-120b"
    assert request["reasoning_effort"] == "low"
    assert request["include_reasoning"] is False
    assert request["max_completion_tokens"] == 512
    assert set(request) == {
        "model",
        "messages",
        "reasoning_effort",
        "include_reasoning",
        "max_completion_tokens",
    }
    assert "fake-key" not in json.dumps(result)
    assert "private response" not in json.dumps(result)

    request_ollama = Mock(
        return_value={"done": True, "done_reason": "stop", "response": "Nieuws."}
    )
    monkeypatch.setattr(
        "Backend.Logic.ollama_client.OllamaClient._json_request", request_ollama
    )
    assert job.build_service(settings, "ollama").candidate(story)["status"] == "success"
    path, payload = request_ollama.call_args.args
    assert path == "/api/generate"
    assert payload["model"] == "llama3.2:3b"
    assert payload["options"] == {"temperature": 0, "num_ctx": 32768}
    assert payload["truncate"] is False and payload["shift"] is False
    assert "format" not in payload


def test_conflicting_group_and_oversized_input_skip_generation():
    generate = Mock()
    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    left, right = linked_article(1), linked_article(2)
    left.article.title = "Burgemeestersvacature Utrecht"
    right.article.title = "Burgemeestersvacature Rotterdam"
    result = service.candidate(published_story(left, right))
    assert result["reason"] == "conflicting_story_group"

    oversized = published_story(linked_article(1, "x" * 33000))
    result = service.candidate(oversized)
    assert result["reason"] == "model_context_limit"
    generate.assert_not_called()


def test_pilot_rolls_back_before_generation_and_saves_separately(monkeypatch, tmp_path):
    story = published_story(linked_article(1))
    story.summary = "Bestaande samenvatting."
    session = MagicMock()
    session.__enter__.return_value = session
    session.get_bind.return_value.dialect.name = "postgresql"
    session.scalar.return_value = "on"
    monkeypatch.setattr(job.StoryRepository, "get", Mock(return_value=story))
    monkeypatch.setattr(job, "RESULTS", tmp_path)

    def generate(_prompt):
        session.rollback.assert_called_once()
        session.__exit__.assert_called_once()
        return {"text": "Nieuw concept.", "finish_reason": "stop"}

    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    assert job.summarize_stories([story.id, story.id], service, lambda: session) == 0
    (output,) = tmp_path.glob("*.json")
    assert json.loads(output.read_text(encoding="utf-8"))["summary"] == "Nieuw concept."
    assert story.summary == "Bestaande samenvatting."
    options = session.connection.call_args.kwargs["execution_options"]
    assert options["postgresql_readonly"] is True
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.add.assert_not_called()
    session.execute.assert_not_called()
