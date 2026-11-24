import hashlib
import time
from collections.abc import Callable
from itertools import combinations

from Backend.Logic.ai_service import AIModelError
from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.story_grouping import MIN_SCORE, event_conflict
from Backend.Logic.story_summary_prompts import (
    MULTI_ARTICLE_INSTRUCTION,
    SINGLE_ARTICLE_INSTRUCTION,
)

MAX_SUMMARY_CHARS = 2500
GROQ_CONTEXT = 131_072
OLLAMA_OUTPUT_RESERVE = 4096


def build_story_summary_prompt(title: str, sources: list[dict]) -> str:
    instruction = (
        SINGLE_ARTICLE_INSTRUCTION if len(sources) == 1 else MULTI_ARTICLE_INSTRUCTION
    )
    blocks = []
    for index, source in enumerate(sources, 1):
        blocks.append(
            "\n".join(
                (
                    f"ARTICLE {index}",
                    f"Article ID: {source['article_id']}",
                    f"Title: {source['title']}",
                    f"Publisher: {source['publisher']}",
                    f"Publication time: {source['published_at'] or 'unknown'}",
                    f"Primary Article: {'yes' if source['is_primary'] else 'no'}",
                    "Full body:",
                    source["body"],
                )
            )
        )
    return "\n\n".join((instruction, f"STORY TITLE: {title}", *blocks))


def story_summary_sources(story: StoryDetails) -> tuple[list, list[dict]]:
    links = sorted(
        story.articles,
        key=lambda link: (
            link.article.published_at is None,
            link.article.published_at,
            str(link.article.id),
        ),
    )
    sources = [
        {
            "article_id": str(link.article.id),
            "title": link.article.title,
            "publisher": link.article.provider.name,
            "published_at": (
                link.article.published_at.isoformat()
                if link.article.published_at
                else None
            ),
            "is_primary": link.is_primary,
            "body": link.article.content or "",
        }
        for link in links
    ]
    return links, sources


class StorySummarizationService:
    def __init__(
        self, generate: Callable[[str], dict], provider: str, model: str, settings: dict
    ):
        self.generate = generate
        self.provider = provider
        self.model = model
        self.settings = settings

    def candidate(self, story: StoryDetails) -> dict:
        record = {
            "story_id": str(story.id),
            "story_title": story.title,
            "provider": self.provider,
            "model": self.model,
            "settings": self.settings,
            "status": "skipped",
            "summary": None,
        }
        if story.status != StoryStatus.published:
            return dict(record, reason="story_not_published")
        if not story.title.strip() or not story.articles:
            return dict(record, reason="missing_title_or_articles")

        links, sources = story_summary_sources(story)
        record.update(
            articles=[
                {key: value for key, value in source.items() if key != "body"}
                for source in sources
            ],
            prompt_version=(
                "single_article_v1" if len(links) == 1 else "multiple_articles_v1"
            ),
        )
        if any(not source["body"].strip() for source in sources):
            return dict(record, reason="missing_article_body")
        if any(
            event_conflict(left.article, right.article)
            for left, right in combinations(links, 2)
        ):
            return dict(record, reason="conflicting_story_group")
        if any(
            not link.is_primary
            and link.similarity_score is not None
            and link.similarity_score < MIN_SCORE
            for link in links
        ):
            record["review_flags"] = ["low_secondary_similarity"]

        prompt = build_story_summary_prompt(story.title, sources)
        prompt_bytes = prompt.encode("utf-8")
        size = len(prompt_bytes)
        estimate = (size + 2) // 3 + 64
        record.update(
            input_sha256=hashlib.sha256(prompt_bytes).hexdigest(),
            estimated_input_tokens=estimate,
        )
        if self.provider == "groq":
            cap = self.settings["max_completion_tokens"]
            if size + 64 + cap > GROQ_CONTEXT:
                return dict(record, reason="model_context_limit")
            if estimate + cap > self.settings["token_budget"]:
                return dict(record, reason="estimated_groq_token_limit")
        elif size + 64 + OLLAMA_OUTPUT_RESERVE > self.settings["num_ctx"]:
            return dict(record, reason="model_context_limit")
        return self._generate_candidate(prompt, record)

    def _generate_candidate(self, prompt: str, record: dict) -> dict:
        started = time.perf_counter()
        record["status"] = "failed"
        try:
            output = self.generate(prompt)
            summary = output.get("text")
            finish = output.get("finish_reason")
            record.update(
                finish_reason=finish,
                usage=output.get("usage"),
                reported_model=output.get("reported_model"),
            )
            if finish != "stop":
                record["reason"] = "incomplete_output"
            elif not isinstance(summary, str) or not summary.strip():
                record["reason"] = "empty_output"
            elif len(summary.strip()) > MAX_SUMMARY_CHARS:
                record["reason"] = "summary_too_long"
            else:
                record.update(status="success", summary=summary.strip())
        except AIModelError as exc:
            record.update(reason="provider_error", error=str(exc))
            if getattr(exc, "status_code", None) is not None:
                record["provider_http_status"] = exc.status_code
        finally:
            record["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        return record
