import json
from datetime import datetime, timezone
from types import SimpleNamespace

from Backend.jobs.grouping_review import preview_review
from Backend.Logic.story_grouping import MIN_SCORE, assess_story


def article(key):
    return SimpleNamespace(
        id=key, title=f"Headline {key}", provider=SimpleNamespace(name="Test provider"),
        canonical_url=f"https://example.test/{key}", published_at=None,
        description=None, content=None,
        first_seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_assessment_distinguishes_rejections():
    incoming, candidate = article(1), article(2)
    vectors = {1: {"a": 1}, 2: {"a": MIN_SCORE / 2}}
    groups = {2: (candidate, [candidate])}
    assert assess_story(incoming, {}, vectors)["reason"] == "no candidate on the same publication day"
    assert assess_story(incoming, groups, vectors)["reason"] == "below threshold"
    vectors[2] = {"a": 1}
    groups[3] = (candidate, [candidate])
    assert assess_story(incoming, groups, vectors)["reason"] == "too close to the runner-up"


def test_preview_exports_reviewable_pairs_and_explains_later_match(tmp_path, capsys):
    first, second, third = article(1), article(2), article(3)
    groups = {1: (first, [first, second]), 3: (third, [third])}
    vectors = {1: {"a": 1}, 2: {"a": 1}, 3: {"a": 1}}
    path = tmp_path / "review.json"
    sample = preview_review(groups, vectors, {1, 3},
                            {3: "no candidate on the same publication day"}, output=path)
    assert len(sample) == 2
    assert sample[1]["comparison"]["id"] == "1"
    assert sample[1]["reason"].startswith("would match after batch")
    assert sample[1]["label"] == ""
    assert json.loads(path.read_text(encoding="utf-8"))["pairs"] == sample
    output = capsys.readouterr().out
    assert "Test provider" in output
    assert "first seen fallback" in output
    assert "https://example.test/3" in output
