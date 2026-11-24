import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
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
from Backend.Logic.story_summarization_service import (
    StorySummarizationService,
    build_story_summary_prompt,
    story_summary_sources,
)

RESULTS = (
    Path(__file__).resolve().parents[2]
    / "ai-evaluation"
    / "story-summary-integration"
    / "results"
)
MAX_STORIES = 10


def open_read_only(db) -> None:
    if db.get_bind().dialect.name != "postgresql":
        raise RuntimeError("Story summarization requires PostgreSQL")
    db.connection(
        execution_options={
            "isolation_level": "REPEATABLE READ",
            "postgresql_readonly": True,
        }
    )
    if db.scalar(text("SELECT current_setting('transaction_read_only')")) != "on":
        raise RuntimeError("Could not confirm a read-only transaction")


def read_story(story_id: UUID, session_factory) -> StoryDetails:
    with session_factory() as db:
        try:
            open_read_only(db)
            story_service = StoryService(
                StoryRepository(db), ArticleRepository(db), TagRepository(db)
            )
            story = story_service.get_story(story_id)
            if not isinstance(story, StoryDetails):
                raise RuntimeError("Story retrieval did not include linked Articles")
            return story
        finally:
            db.rollback()


def read_result(path: Path) -> dict | None:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Invalid result")
        return record
    except (OSError, ValueError):
        print(f"Invalid or unreadable result: {path.name}")
        return None


def iter_results(directory: Path):
    for path in sorted(directory.glob("*.json")):
        if path.name.endswith(".reconciliation.json"):
            continue
        record = read_result(path)
        try:
            UUID(record["story_id"])
        except (KeyError, TypeError, ValueError, AttributeError):
            if record is not None:
                print(f"Invalid Story ID in result: {path.name}")
            continue
        if record.get("status") not in ("success", "skipped", "failed"):
            print(f"Invalid generation status in result: {path.name}")
            continue
        yield path, record


def _reconcile_saves(repository, uncertain, excluded):
    for story_id, path, record in uncertain:
        reconciliation = path.with_suffix(".reconciliation.json")
        if reconciliation.exists():
            previous = read_result(reconciliation)
            if not previous or previous.get("outcome") != "not_stored":
                excluded.add(story_id)
            continue
        story = repository.get(story_id)
        stored = story.summary if story is not None else None
        generated = record.get("summary")
        if stored and stored.strip():
            outcome = "confirmed_saved" if stored == generated else "different_summary"
            excluded.add(story_id)
        else:
            outcome = "not_stored"
        write_result(
            reconciliation,
            {
                "story_id": str(story_id),
                "result_file": path.name,
                "outcome": outcome,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        print(f"{story_id}: previous save reconciled ({outcome})")


def _exclude_unchanged_input_limits(repository, latest, service, excluded):
    for story_id, record in latest.items():
        if (
            story_id not in excluded
            and record.get("reason")
            in {"model_context_limit", "estimated_groq_token_limit"}
            and record.get("provider") == service.provider
            and record.get("model") == service.model
            and isinstance(record.get("settings"), dict)
            and all(
                record["settings"].get(key) == service.settings.get(key)
                for key in ("num_ctx", "token_budget", "max_completion_tokens")
            )
        ):
            story = repository.get(story_id)
            if isinstance(story, StoryDetails):
                _, sources = story_summary_sources(story)
                prompt = build_story_summary_prompt(story.title, sources)
                if hashlib.sha256(prompt.encode("utf-8")).hexdigest() == record.get(
                    "input_sha256"
                ):
                    excluded.add(story_id)


def select_backfill_ids(
    limit: int, session_factory, service: StorySummarizationService
) -> list[UUID]:
    latest = {}
    uncertain = []
    excluded = set()
    for path, record in iter_results(RESULTS):
        story_id = UUID(record["story_id"])
        status = record.get("database_status")
        if record.get("backfill"):
            latest[story_id] = record
        if status == "saved" and record.get("database_verification") == "matched":
            excluded.add(story_id)
        elif status == "pending" or (
            status in {"saved", "failed"} and record.get("status") == "success"
        ):
            uncertain.append((story_id, path, record))

    with session_factory() as db:
        try:
            open_read_only(db)
            repository = StoryRepository(db)
            _reconcile_saves(repository, uncertain, excluded)
            _exclude_unchanged_input_limits(repository, latest, service, excluded)

            selected = repository.list_summary_candidate_ids(
                limit=limit, excluded_ids=excluded | latest.keys()
            )
            if len(selected) < limit:
                selected += repository.list_summary_candidate_ids(
                    limit=limit - len(selected), excluded_ids=excluded | set(selected)
                )
            return selected
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
    story_ids: list[UUID],
    service: StorySummarizationService,
    session_factory,
    *,
    save: bool = False,
    backfill: bool = False,
) -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    failures = 0
    consecutive_provider_errors = 0
    for story_id in dict.fromkeys(story_ids):
        record = _generate_candidate(story_id, service, session_factory)
        consecutive_provider_errors, stop_reason = _provider_progress(
            record, consecutive_provider_errors
        )
        failures += _record_story_result(
            story_id, record, service, session_factory, save=save, backfill=backfill
        )
        if stop_reason:
            print(f"Stopped before remaining Stories ({stop_reason}).")
            break
    return failures


def _generate_candidate(story_id, service, session_factory):
    try:
        story = read_story(story_id, session_factory)
    except NotFoundError:
        return {"status": "skipped", "reason": "story_not_found"}
    except (SQLAlchemyError, RuntimeError):
        return {"status": "failed", "reason": "database_read_failed"}
    if story.summary and story.summary.strip():
        return {"status": "skipped", "reason": "already_summarized"}
    return service.candidate(story)


def _provider_progress(record, consecutive_errors):
    if record.get("reason") != "provider_error":
        return (0 if record["status"] == "success" else consecutive_errors), None

    code = record.get("provider_http_status")
    if code in {401, 402, 403, 429}:
        return consecutive_errors, f"HTTP {code}"
    if code not in {400, 413, 422}:
        consecutive_errors += 1
        if consecutive_errors >= 2:
            return consecutive_errors, "repeated provider errors"
    return consecutive_errors, None


def _save_and_verify(story_id, record, session_factory, *, backfill):
    outcome = save_summary(story_id, record, session_factory)
    record["database_status"] = outcome if outcome in {"saved", "failed"} else "skipped"
    record["database_reason"] = outcome
    if not backfill or outcome != "saved":
        return outcome

    try:
        stored = read_story(story_id, session_factory)
    except (NotFoundError, SQLAlchemyError, RuntimeError):
        record["database_verification"] = "read_failed"
    else:
        record["database_verification"] = (
            "matched" if stored.summary == record["summary"] else "mismatch"
        )
    return outcome


def _record_story_result(story_id, record, service, session_factory, *, save, backfill):
    should_save = save and record["status"] == "success"
    record["database_status"] = (
        "pending" if should_save else "skipped" if save else "not_requested"
    )
    stamp = datetime.now(timezone.utc)
    record.update(
        story_id=str(story_id),
        created_at_utc=stamp.isoformat(),
        provider=service.provider,
        model=service.model,
        settings=service.settings,
    )
    if backfill:
        record["backfill"] = True
    path = RESULTS / f"{stamp:%Y%m%dT%H%M%S%fZ}_{story_id}_{service.provider}.json"
    try:
        write_result(path, record)
    except OSError:
        print(f"{story_id}: failed (local_result_write_failed)")
        return True

    if should_save:
        outcome = _save_and_verify(story_id, record, session_factory, backfill=backfill)
        # Preserve the original result if writing the final status fails.
        try:
            write_result(path, record, replace=True)
        except OSError:
            print(
                f"{story_id}: failed (local_status_write_failed, database outcome: {outcome})"
            )
            return True

    reason = record.get("database_reason", record.get("reason", "candidate saved"))
    verification = record.get("database_verification")
    if verification and verification != "matched":
        reason = verification
    print(
        f"{story_id}: {record['status']} / {record['database_status']} ({reason}) – {path}"
    )
    return (
        record["status"] == "failed"
        or record["database_status"] == "failed"
        or verification in {"read_failed", "mismatch"}
    )


def write_result(path: Path, record: dict, *, replace: bool = False) -> None:
    contents = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as file:
            temporary = Path(file.name)
            file.write(contents)
            file.flush()
            os.fsync(file.fileno())
        if replace:
            temporary.replace(path)
        else:
            os.link(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def save_summary(story_id: UUID, record: dict, session_factory) -> str:
    try:
        with session_factory() as db, db.begin():
            db.connection(execution_options={"isolation_level": "READ COMMITTED"})
            stories = StoryService(
                StoryRepository(db), ArticleRepository(db), TagRepository(db)
            )
            outcome = stories.save_generated_summary(
                story_id, record["summary"], record["input_sha256"]
            )
    except (SQLAlchemyError, RuntimeError):
        return "failed"
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate local candidates for explicit Story IDs."
    )
    parser.add_argument("story_ids", type=UUID, nargs="*")
    parser.add_argument("--backfill", type=int, metavar="LIMIT")
    parser.add_argument("--provider", choices=("groq", "ollama"))
    parser.add_argument(
        "--save", action="store_true", help="Save valid summaries to the database."
    )
    args = parser.parse_args()
    if bool(args.story_ids) == (args.backfill is not None):
        parser.error("Pass explicit Story IDs or --backfill LIMIT")
    if args.backfill is not None and (
        not 1 <= args.backfill <= MAX_STORIES or not args.save
    ):
        parser.error(f"--backfill requires --save and a limit from 1 to {MAX_STORIES}")
    if len(args.story_ids) > MAX_STORIES:
        parser.error(f"Pass at most {MAX_STORIES} Story IDs")
    settings = get_settings()
    try:
        provider = args.provider or settings.story_summary_provider
        service = build_service(settings, provider)
    except ValueError as exc:
        parser.error(str(exc))

    from Backend.database import SessionLocal

    story_ids = args.story_ids
    if args.backfill is not None:
        try:
            story_ids = select_backfill_ids(args.backfill, SessionLocal, service)
        except (
            OSError,
            ValueError,
            KeyError,
            AttributeError,
            SQLAlchemyError,
            RuntimeError,
        ) as exc:
            parser.exit(1, f"Backfill selection failed ({type(exc).__name__}).\n")
        if not story_ids:
            print("No unattempted eligible Stories found.")
            return 0
    return int(
        bool(
            summarize_stories(
                story_ids,
                service,
                SessionLocal,
                save=args.save,
                backfill=args.backfill is not None,
            )
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
