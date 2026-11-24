import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from Backend.config import Settings, get_settings
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository
from Backend.Dal.repositories.tag_repository import TagRepository
from Backend.Logic.domain.story import StoryDetails
from Backend.Logic.exceptions import NotFoundError
from Backend.Logic.groq_client import (
    GROQ_SUMMARY_MODEL,
    GROQ_SUMMARY_OPTIONS,
    GroqClient,
)
from Backend.Logic.ollama_client import STORY_SUMMARY_OPTIONS, OllamaClient
from Backend.Logic.story_service import StoryService
from Backend.Logic.story_summarization_service import StorySummarizationService

RESULTS = (
    Path(__file__).resolve().parents[2]
    / "ai-evaluation"
    / "story-summary-integration"
    / "results"
)
MAX_STORIES = 10


def read_story(story_id: UUID, session_factory) -> StoryDetails:
    with session_factory() as db:
        try:
            if db.get_bind().dialect.name != "postgresql":
                raise RuntimeError("The pilot requires read-only PostgreSQL access")
            db.connection(
                execution_options={
                    "isolation_level": "REPEATABLE READ",
                    "postgresql_readonly": True,
                }
            )
            read_only = db.scalar(text("SELECT current_setting('transaction_read_only')"))
            if read_only != "on":
                raise RuntimeError("Could not confirm a read-only transaction")
            story_service = StoryService(
                StoryRepository(db), ArticleRepository(db), TagRepository(db)
            )
            story = story_service.get_story(story_id)
            if not isinstance(story, StoryDetails):
                raise RuntimeError("Story retrieval did not include linked Articles")
            return story
        finally:
            db.rollback()


def build_service(settings: Settings, provider: str) -> StorySummarizationService:
    if provider == "groq":
        key = settings.groq_api_key
        if key is None or not key.get_secret_value().strip():
            raise ValueError("GROQ_API_KEY is required for Groq Story Summarization")
        client = GroqClient(key.get_secret_value().strip())
        return StorySummarizationService(
            client.generate_story_summary,
            provider,
            GROQ_SUMMARY_MODEL,
            {
                **GROQ_SUMMARY_OPTIONS,
                "token_budget": settings.story_summary_groq_token_budget,
                "timeout_seconds": client.timeout_seconds,
                "attempt_limit": 1,
            },
        )
    if provider != "ollama":
        raise ValueError("Unknown Story Summarization provider")
    model = "llama3.2:3b"
    client = OllamaClient(settings.ollama_base_url, model, timeout_seconds=900)
    return StorySummarizationService(
        client.generate_story_summary,
        provider,
        model,
        {
            **STORY_SUMMARY_OPTIONS,
            "timeout_seconds": client.timeout_seconds,
            "stream": False,
            "truncate": False,
            "shift": False,
        },
    )


def summarize_stories(
    story_ids: list[UUID], service: StorySummarizationService, session_factory
) -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    failures = 0
    for story_id in dict.fromkeys(story_ids):
        try:
            story = read_story(story_id, session_factory)
        except NotFoundError:
            record = {"status": "skipped", "reason": "story_not_found"}
        except (SQLAlchemyError, RuntimeError):
            record = {"status": "failed", "reason": "database_read_failed"}
        else:
            record = service.candidate(story)

        stamp = datetime.now(timezone.utc)
        record.update(
            story_id=str(story_id),
            created_at_utc=stamp.isoformat(),
            provider=service.provider,
            model=service.model,
            settings=service.settings,
        )
        path = RESULTS / f"{stamp:%Y%m%dT%H%M%S%fZ}_{story_id}_{service.provider}.json"
        with path.open("x", encoding="utf-8") as file:
            json.dump(record, file, ensure_ascii=False, indent=2)
            file.write("\n")
        reason = record.get("reason", "candidate saved")
        print(f"{story_id}: {record['status']} ({reason}) – {path}")
        failures += record["status"] == "failed"
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local candidates for explicit Story IDs."
    )
    parser.add_argument("story_ids", type=UUID, nargs="+")
    parser.add_argument("--provider", choices=("groq", "ollama"))
    args = parser.parse_args()
    if len(args.story_ids) > MAX_STORIES:
        parser.error(f"Pass at most {MAX_STORIES} Story IDs")
    settings = get_settings()
    try:
        provider = args.provider or settings.story_summary_provider
        service = build_service(settings, provider)
    except ValueError as exc:
        parser.error(str(exc))

    from Backend.database import SessionLocal

    return int(bool(summarize_stories(args.story_ids, service, SessionLocal)))


if __name__ == "__main__":
    raise SystemExit(main())
