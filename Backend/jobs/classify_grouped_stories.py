import uuid
from collections.abc import Callable, Iterable

from sqlalchemy.orm import Session

from Backend.config import get_settings
from Backend.Dal.repositories.article_repository import ArticleRepository
from Backend.Dal.repositories.story_repository import StoryRepository
from Backend.Dal.repositories.tag_repository import TagRepository
from Backend.Logic.genre_classification_service import GenreClassificationService
from Backend.Logic.genre_classification_tag_adapter import (
    GenreClassificationTagAdapter,
    MissingGenreTagError,
)
from Backend.Logic.story_service import StoryService


def _load_classifier() -> GenreClassificationService:
    settings = get_settings()
    if settings.genre_classification_model_path is None:
        raise ValueError("GENRE_CLASSIFICATION_MODEL_PATH is required")
    return GenreClassificationService.from_checkpoint(
        settings.genre_classification_model_path,
        device_name=settings.genre_classification_device,
    )


def classify_grouped_stories(
    story_ids: Iterable[uuid.UUID | str],
    *,
    session_factory: Callable[[], Session],
    load_classifier: Callable[[], GenreClassificationService] = _load_classifier,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {"processed": {}, "skipped": {}, "failed": {}}
    candidates = {}
    for value in story_ids:
        try:
            story_id = uuid.UUID(str(value))
        except ValueError:
            invalid_id = f"invalid-id-{len(result['failed']) + 1}"
            result["failed"][invalid_id] = "invalid Story ID"
            continue
        candidates[story_id] = str(story_id)

    if not candidates:
        return result

    try:
        classifier = load_classifier()
    except Exception:
        result["failed"].update(dict.fromkeys(candidates.values(), "model load failed"))
        return result

    for story_id, key in candidates.items():
        try:
            with session_factory() as db:
                snapshot = StoryRepository(db).get(story_id)
        except Exception:
            result["failed"][key] = "Story read failed"
            continue
        if snapshot is None or snapshot.tags:
            result["skipped"][key] = "missing" if snapshot is None else "already_tagged"
            continue

        try:
            predictions = classifier.classify(
                title=snapshot.title, summary=snapshot.summary, context=snapshot.context,
            )
        except Exception:
            result["failed"][key] = "inference failed"
            continue
        if not predictions:
            result["skipped"][key] = "no predictions"
            continue

        try:
            with session_factory() as db, db.begin():
                tags = TagRepository(db)
                resolved = GenreClassificationTagAdapter(tags).to_story_tags(predictions)
                stories = StoryService(StoryRepository(db), ArticleRepository(db), tags)
                outcome = stories.add_genre_tags_if_current(snapshot, resolved)
        except MissingGenreTagError:
            result["failed"][key] = "missing genre in database vocabulary"
        except Exception:
            result["failed"][key] = "tag write failed"
        else:
            result["processed" if outcome == "saved" else "skipped"][key] = outcome

    return result
