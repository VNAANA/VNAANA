import csv
import hashlib
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock
from uuid import UUID

import httpx
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError

from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.domain.story_articles import StoryArticleDetails
from Backend.Logic.story_service import StoryService
from Backend.Logic.story_summarization_service import (
    StorySummarizationService,
    build_story_summary_prompt,
    story_summary_sources,
)
from Backend.Logic.story_summary_prompts import (
    MULTI_ARTICLE_INSTRUCTION,
    SINGLE_ARTICLE_INSTRUCTION,
)
from Backend.config import Settings
from Backend.jobs.export_story_summary_results import export_results
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


def test_backfill_selection_filters_and_orders_candidates():
    session = Mock()
    session.scalars.return_value = [UUID(int=9), UUID(int=10)]
    repo = job.StoryRepository(session)
    assert repo.list_summary_candidate_ids(limit=2, excluded_ids={UUID(int=1)}) == [
        UUID(int=9), UUID(int=10)
    ]
    stmt = session.scalars.call_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    sql = str(compiled)
    assert "stories.status = 'published'" in sql
    assert "coalesce(stories.summary" in sql
    assert "EXISTS (SELECT story_articles.article_id" in sql
    assert "JOIN articles" in sql and "coalesce(articles.content" in sql
    assert "NOT IN" in sql and str(UUID(int=1)) in sql
    assert "ORDER BY stories.first_published_at ASC NULLS LAST, stories.id" in sql
    assert "LIMIT 2" in sql


def test_backfill_resumes_from_local_results(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(job, "RESULTS", tmp_path)
    for number, status in [(1, "saved"), (2, "pending"), (3, "not_requested"), (4, "failed"), (5, "pending")]:
        (tmp_path / f"{number}.json").write_text(json.dumps({
            "story_id": str(UUID(int=number)), "database_status": status,
            "backfill": number != 3, "summary": "Het nieuws.",
            "status": "failed" if number == 4 else "success",
            "database_verification": "matched" if number == 1 else None,
        }), encoding="utf-8")
    db = MagicMock()
    db.__enter__.return_value = db
    db.get_bind.return_value.dialect.name = "postgresql"
    db.scalar.return_value = "on"
    repo = Mock()
    repo.get.side_effect = [
        SimpleNamespace(summary="Het nieuws."),
        SimpleNamespace(summary="Andere tekst."),
    ]
    repo.list_summary_candidate_ids.side_effect = [[], [UUID(int=4)]]
    monkeypatch.setattr(job, "StoryRepository", lambda _: repo)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    original = (tmp_path / "2.json").read_bytes()

    assert job.select_backfill_ids(2, lambda: db, Mock()) == [UUID(int=4)]
    assert repo.list_summary_candidate_ids.call_args.kwargs["excluded_ids"] == {
        UUID(int=1), UUID(int=2), UUID(int=5)
    }
    for number, outcome in [(2, "confirmed_saved"), (5, "different_summary")]:
        result = json.loads((tmp_path / f"{number}.reconciliation.json").read_text())
        assert result["outcome"] == outcome
    assert (tmp_path / "2.json").read_bytes() == original
    assert "broken.json" in capsys.readouterr().out
    db.rollback.assert_called_once()


@pytest.mark.parametrize("change", [None, "body", "settings"])
def test_input_limit_retries_only_after_change(tmp_path, monkeypatch, change):
    story = published_story(linked_article(1))
    _, sources = story_summary_sources(story)
    old_hash = hashlib.sha256(build_story_summary_prompt(story.title, sources).encode()).hexdigest()
    record = {
        "story_id": str(story.id), "backfill": True, "status": "skipped",
        "reason": "model_context_limit", "provider": "ollama", "model": "llama3.2:3b",
        "settings": {"num_ctx": 32768}, "input_sha256": old_hash,
    }
    job.write_result(tmp_path / "old.json", record)
    monkeypatch.setattr(job, "RESULTS", tmp_path)
    if change == "body":
        story.articles[0].article.content = "Gewijzigd."
    service = StorySummarizationService(
        Mock(), "ollama", "llama3.2:3b", {"num_ctx": 65536 if change == "settings" else 32768}
    )
    db = MagicMock()
    db.__enter__.return_value = db
    db.get_bind.return_value.dialect.name = "postgresql"
    db.scalar.return_value = "on"
    repo = Mock()
    repo.get.return_value = story
    repo.list_summary_candidate_ids.side_effect = lambda *, limit, excluded_ids: (
        [] if story.id in excluded_ids else [story.id]
    )
    monkeypatch.setattr(job, "StoryRepository", lambda _: repo)
    assert job.select_backfill_ids(1, lambda: db, service) == ([story.id] if change else [])


def test_initial_result_is_complete_before_publish_and_unique(tmp_path, monkeypatch):
    path = tmp_path / "result.json"
    original_link = job.os.link

    def inspect(temp, target):
        assert json.loads(temp.read_text(encoding="utf-8")) == {"status": "success"}
        original_link(temp, target)

    monkeypatch.setattr(job.os, "link", inspect)
    job.write_result(path, {"status": "success"})
    with pytest.raises(FileExistsError):
        job.write_result(path, {"status": "success"})
    assert list(tmp_path.iterdir()) == [path]


def test_provider_quota_stops_before_remaining_stories(tmp_path, monkeypatch):
    from Backend.Logic.groq_client import GroqRequestError

    story = published_story(linked_article(1))
    second = published_story(linked_article(2))
    second.id = UUID(int=10)
    provider = Mock(side_effect=GroqRequestError(429))
    service = StorySummarizationService(
        provider, "groq", "openai/gpt-oss-120b",
        {"max_completion_tokens": 512, "token_budget": 8000},
    )
    monkeypatch.setattr(job, "RESULTS", tmp_path)
    read = Mock(return_value=story)
    monkeypatch.setattr(job, "read_story", read)
    assert job.summarize_stories([story.id, second.id], service, Mock(), save=True) == 1
    read.assert_called_once()
    (path,) = tmp_path.glob("*.json")
    assert json.loads(path.read_text())["provider_http_status"] == 429


def test_csv_retains_attempts_unicode_and_review_notes(tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    source = {
        "story_id": str(UUID(int=9)), "summary": 'België, "nieuws".\nEen vervolg.',
        "articles": [{"article_id": str(UUID(int=1)), "publisher": "NOS", "body": "Private body"}],
        "status": "success", "elapsed_seconds": 0.5,
    }
    for name in ("b.json", "a.json"):
        (results / name).write_text(json.dumps(source), encoding="utf-8")
    (results / "broken.json").write_text("{", encoding="utf-8")
    before = {path: path.read_bytes() for path in results.iterdir()}
    output = tmp_path / "evaluation.csv"
    assert export_results(results, output) == 2
    with output.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)
        fields = reader.fieldnames
    assert [row["result_file"] for row in rows] == ["a.json", "b.json"]
    assert rows[0]["generated_summary"] == source["summary"]
    assert rows[0]["article_count"] == "1"
    assert rows[0]["database_status"] == ""
    rows[0]["review_notes"] = "Handmatig gecontroleerd"
    with output.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert export_results(results, output) == 2
    with output.open(encoding="utf-8-sig", newline="") as file:
        assert list(csv.DictReader(file)) == rows
    assert "Private body" not in output.read_text(encoding="utf-8-sig")
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize(
    ("change", "outcome"),
    [
        ("body", "stale"),
        ("membership", "stale"),
        ("existing", "already_summarized"),
        ("draft", "unpublished"),
        (None, "saved"),
    ],
)
def test_save_rechecks_story_and_evidence(change, outcome):
    story = published_story(linked_article(1))
    _, sources = story_summary_sources(story)
    input_hash = hashlib.sha256(
        build_story_summary_prompt(story.title, sources).encode()
    ).hexdigest()
    if change == "body":
        story.articles[0].article.content = "Gewijzigde tekst."
    elif change == "membership":
        story.articles.append(linked_article(2))
    elif change == "existing":
        story.summary = "Een eerdere samenvatting."
    elif change == "draft":
        story.status = StoryStatus.draft

    repo = Mock()
    repo.get_for_summary_publication.return_value = story
    service = StoryService(repo, Mock(), Mock())
    assert service.save_generated_summary(story.id, "Het nieuws.", input_hash) == outcome
    if outcome == "saved":
        assert repo.update.call_args.args == (story,)
        fields = repo.update.call_args.kwargs
        assert fields["summary"] == "Het nieuws."
        assert fields["last_updated_at"] > story.last_updated_at
        assert set(fields) == {"summary", "last_updated_at"}
    else:
        repo.update.assert_not_called()


def test_batch_preserves_candidates_and_continues_after_database_failure(
    tmp_path, monkeypatch
):
    first = published_story(linked_article(1))
    second = published_story(linked_article(1), linked_article(2))
    second.id = UUID(int=10)
    existing = published_story(linked_article(1))
    existing.id = UUID(int=11)
    existing.summary = "Een eerdere samenvatting."
    empty = published_story(linked_article(1))
    empty.id = UUID(int=12)
    generate = Mock(side_effect=[
        {"text": "Eerste.", "finish_reason": "stop"},
        {"text": "Tweede.", "finish_reason": "stop"},
        {"text": "", "finish_reason": "stop"},
    ])
    service = StorySummarizationService(
        generate, "ollama", "llama3.2:3b", {"num_ctx": 32768}
    )
    sessions = [MagicMock(), MagicMock()]
    error = OperationalError("lock", {}, RuntimeError("lock unavailable"))
    for session in sessions:
        session.__enter__.return_value = session
        session.get_bind.return_value.dialect.name = "postgresql"
    sessions[0].scalar.side_effect = error
    sessions[1].scalar.return_value = second.id
    monkeypatch.setattr(job, "RESULTS", tmp_path)
    monkeypatch.setattr(job, "read_story", Mock(side_effect=[
        first, second, SimpleNamespace(summary="Tweede."), existing, empty,
    ]))
    monkeypatch.setattr(job.StoryRepository, "get", Mock(return_value=second))
    update = Mock()
    monkeypatch.setattr(job.StoryRepository, "update", update)
    factory = Mock(side_effect=sessions)

    assert job.summarize_stories(
        [first.id, second.id, existing.id, empty.id], service, factory,
        save=True, backfill=True,
    ) == 2
    results = {
        record["story_id"]: record
        for path in tmp_path.glob("*.json")
        if (record := json.loads(path.read_text(encoding="utf-8")))
    }
    assert results[str(first.id)]["database_status"] == "failed"
    assert results[str(first.id)]["summary"] == "Eerste."
    assert results[str(second.id)]["database_status"] == "saved"
    assert results[str(second.id)]["summary"] == "Tweede."
    assert results[str(second.id)]["database_verification"] == "matched"
    assert results[str(existing.id)]["reason"] == "already_summarized"
    assert results[str(empty.id)]["reason"] == "empty_output"
    assert results[str(empty.id)]["database_status"] == "skipped"
    assert generate.call_count == 3
    assert factory.call_count == 2
    assert sessions[0].begin.return_value.__exit__.call_args.args[1] is error
    assert sessions[1].begin.return_value.__exit__.call_args.args == (None, None, None)
    lock = sessions[0].scalar.call_args.args[0].compile(dialect=postgresql.dialect())
    assert "FOR UPDATE NOWAIT" in str(lock)
    sessions[0].execute.assert_not_called()
    update.assert_called_once()


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
    assert story.summary is None
    assert json.loads(output.read_text(encoding="utf-8"))["database_status"] == "not_requested"
    options = session.connection.call_args.kwargs["execution_options"]
    assert options["postgresql_readonly"] is True
    session.commit.assert_not_called()
    session.flush.assert_not_called()
    session.add.assert_not_called()
    session.execute.assert_not_called()
