import uuid

import pytest

from Backend.Logic.domain.tag import Tag
from Backend.Logic.genre_classification_service import GenrePrediction
from Backend.Logic.genre_classification_tag_adapter import (
    GenreClassificationTagAdapter,
    MissingGenreTagError,
)


class FakeTagRepository:
    def __init__(self, *tags: Tag):
        self.by_name = {tag.name: tag for tag in tags}
        self.lookups: list[str] = []

    def get_by_name(self, name: str) -> Tag | None:
        self.lookups.append(name)
        return self.by_name.get(name)


def make_tag(name: str) -> Tag:
    return Tag(id=uuid.uuid4(), name=name)


def test_resolves_exact_names_and_preserves_scores():
    climate = make_tag("Climate")
    politics = make_tag("Politics")
    tags = FakeTagRepository(climate, politics)
    adapter = GenreClassificationTagAdapter(tags)

    result = adapter.to_story_tags(
        [GenrePrediction("Climate", 0.9123), GenrePrediction("Politics", 0.6789)]
    )

    assert result == {climate.id: 0.9123, politics.id: 0.6789}
    assert tags.lookups == ["Climate", "Politics"]


def test_missing_genre_fails_clearly():
    adapter = GenreClassificationTagAdapter(FakeTagRepository())

    with pytest.raises(MissingGenreTagError, match="'Culture'.*missing"):
        adapter.to_story_tags([GenrePrediction("Culture", 0.81)])


def test_social_issues_is_not_mapped_to_world():
    world = make_tag("World")
    tags = FakeTagRepository(world)
    adapter = GenreClassificationTagAdapter(tags)

    with pytest.raises(MissingGenreTagError, match="'Social Issues'.*missing"):
        adapter.to_story_tags([GenrePrediction("Social Issues", 0.93)])

    assert tags.lookups == ["Social Issues"]


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf")])
def test_rejects_invalid_scores(score):
    adapter = GenreClassificationTagAdapter(FakeTagRepository(make_tag("Science")))

    with pytest.raises(ValueError, match="Invalid score"):
        adapter.to_story_tags([GenrePrediction("Science", score)])


def test_rejects_labels_outside_the_agreed_vocabulary_before_lookup():
    tags = FakeTagRepository()
    adapter = GenreClassificationTagAdapter(tags)

    with pytest.raises(ValueError, match="Unknown VNAANA genre"):
        adapter.to_story_tags([GenrePrediction("World", 0.75)])

    assert tags.lookups == []
