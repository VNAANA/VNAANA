"""Translate genre predictions to the existing StoryService tag input."""

from __future__ import annotations

import math
import uuid
from collections.abc import Sequence

from Backend.Logic.genre_classification_service import GenrePrediction, VNAANA_GENRES
from Backend.Logic.ports.tag_repository import TagRepository


class MissingGenreTagError(RuntimeError):
    """A classifier genre is absent from the configured database vocabulary."""


class GenreClassificationTagAdapter:
    """Resolve exact classifier names to ``{tag_id: relevance_score}``.

    The returned dictionary is the input accepted by ``StoryService.set_tags``.
    This adapter performs no persistence itself.
    """

    def __init__(self, tags: TagRepository):
        self.tags = tags

    def to_story_tags(
        self,
        predictions: Sequence[GenrePrediction],
    ) -> dict[uuid.UUID, float]:
        resolved: dict[uuid.UUID, float] = {}

        for prediction in predictions:
            if prediction.tag not in VNAANA_GENRES:
                raise ValueError(f"Unknown VNAANA genre: {prediction.tag!r}")
            if not math.isfinite(prediction.score) or not 0 <= prediction.score <= 1:
                raise ValueError(
                    f"Invalid score for genre {prediction.tag!r}: {prediction.score}"
                )

            # Exact-name lookup is intentional. In particular, Social Issues is
            # never treated as an alias for the retired World tag.
            tag = self.tags.get_by_name(prediction.tag)
            if tag is None:
                raise MissingGenreTagError(
                    f"Predicted genre {prediction.tag!r} is missing from the tag vocabulary"
                )
            if tag.id in resolved:
                raise ValueError(f"Multiple predictions resolved to tag ID {tag.id}")
            resolved[tag.id] = prediction.score

        return resolved
