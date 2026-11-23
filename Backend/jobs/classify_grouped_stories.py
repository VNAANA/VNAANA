import uuid
from collections.abc import Callable, Iterable
from typing import Any

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


def _collect_candidates(
    story_ids: Iterable[uuid.UUID | str],
    result: dict[str, dict[str, str]],
) -> dict[uuid.UUID, str]:
    candidates = {}

    for value in story_ids:
        try:
            story_id = uuid.UUID(str(value))
        except ValueError:
            invalid_id = f"invalid-id-{len(result['failed']) + 1}"
            result["failed"][invalid_id] = "invalid Story ID"
            continue

        candidates[story_id] = str(story_id)

    return candidates


def _load_classifier_for_candidates(
    candidates: dict[uuid.UUID, str],
    load_classifier: Callable[[], GenreClassificationService],
    result: dict[str, dict[str, str]],
) -> GenreClassificationService | None:
    try:
        return load_classifier()
    except Exception:
        result["failed"].update(dict.fromkeys(candidates.values(), "model load failed"))
        return None


def _load_story_snapshot(
    story_id: uuid.UUID,
    key: str,
    session_factory: Callable[[], Session],
    result: dict[str, dict[str, str]],
) -> tuple[bool, Any]:
    try:
        with session_factory() as db:
            snapshot = StoryRepository(db).get(story_id)
    except Exception:
        result["failed"][key] = "Story read failed"
        return False, None

    return True, snapshot


def _get_predictions(
    snapshot: Any,
    classifier: GenreClassificationService,
    key: str,
    result: dict[str, dict[str, str]],
) -> tuple[bool, Any]:
    try:
        predictions = classifier.classify(
            title=snapshot.title,
            summary=snapshot.summary,
            context=snapshot.context,
        )
    except Exception:
        result["failed"][key] = "inference failed"
        return False, None

    return True, predictions


def _save_genre_tags(
    snapshot: Any,
    predictions: Any,
    key: str,
    session_factory: Callable[[], Session],
    result: dict[str, dict[str, str]],
) -> None:
    try:
        with session_factory() as db, db.begin():
            tags = TagRepository(db)
            resolved = GenreClassificationTagAdapter(tags).to_story_tags(predictions)
            stories = StoryService(
                StoryRepository(db),
                ArticleRepository(db),
                tags,
            )
            outcome = stories.add_genre_tags_if_current(snapshot, resolved)
    except MissingGenreTagError:
        result["failed"][key] = "missing genre in database vocabulary"
    except Exception:
        result["failed"][key] = "tag write failed"
    else:
        result["processed" if outcome == "saved" else "skipped"][key] = outcome


def _process_story(
    story_id: uuid.UUID,
    key: str,
    classifier: GenreClassificationService,
    session_factory: Callable[[], Session],
    result: dict[str, dict[str, str]],
) -> None:
    read_success, snapshot = _load_story_snapshot(
        story_id, key, session_factory, result
    )
    if not read_success:
        return

    if snapshot is None or snapshot.tags:
        result["skipped"][key] = "missing" if snapshot is None else "already_tagged"
        return

    inference_success, predictions = _get_predictions(snapshot, classifier, key, result)
    if not inference_success:
        return

    if not predictions:
        result["skipped"][key] = "no predictions"
        return

    _save_genre_tags(snapshot, predictions, key, session_factory, result)


def classify_grouped_stories(
    story_ids: Iterable[uuid.UUID | str],
    *,
    session_factory: Callable[[], Session],
    load_classifier: Callable[[], GenreClassificationService] = _load_classifier,
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {
        "processed": {},
        "skipped": {},
        "failed": {},
    }

    candidates = _collect_candidates(story_ids, result)
    if not candidates:
        return result

    classifier = _load_classifier_for_candidates(candidates, load_classifier, result)
    if classifier is None:
        return result

    for story_id, key in candidates.items():
        _process_story(story_id, key, classifier, session_factory, result)

    return result
