"""AlgorithmRepository on an in-memory SQLite database.

The algorithm unit tests use a fake repository, so they can't notice a wrong
query. These tests run the real repository against a real database engine and
check every promise the port (Backend/Logic/ports/algorithm_repository.py)
makes.

The database comes from tests/backend/integration/conftest.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from Backend.Dal.models import (
    EngagementEvent,
    EventWeight,
    Story,
    StoryReaction,
    StoryStatus,
    StoryTag,
    Tag,
    User,
    UserTag,
)
from Backend.Dal.repositories.algorithm_repository import AlgorithmRepository
from Backend.Logic.domain.story_reaction import Reaction
from tests.backend.integration.helpers import naive

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=30)


# ---- setup ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def event_types(db):
    # engagement_events.event_type points at event_weights, so the types must exist.
    db.add_all([EventWeight(event_type="share", weight=5), EventWeight(event_type="read_complete", weight=1)])
    db.commit()


@pytest.fixture
def repo(db) -> AlgorithmRepository:
    return AlgorithmRepository(db)


def add_user(db, consent=True, scored_at=None) -> User:
    user = User(
        auth_provider="email",
        auth_subject=str(uuid.uuid4()),
        analytics_consent=consent,
        affinity_updated_at=scored_at,
    )
    db.add(user)
    db.commit()
    return user


def add_tag(db, name) -> Tag:
    tag = Tag(name=name)
    db.add(tag)
    db.commit()
    return tag


def add_story(db, status=StoryStatus.published, updated=NOW, tags=()) -> Story:
    story = Story(title="Story", status=status, last_updated_at=updated)
    db.add(story)
    db.flush()
    db.add_all(StoryTag(story_id=story.id, tag_id=tag.id) for tag in tags)
    db.commit()
    return story


def add_user_tag(db, user, tag, declared, score=0.0, computed_at=None, updated_at=NOW) -> UserTag:
    row = UserTag(
        user_id=user.id,
        tag_id=tag.id,
        is_declared=declared,
        score=score,
        computed_at=computed_at,
        updated_at=updated_at,
    )
    db.add(row)
    db.commit()
    return row


def add_event(db, user, story, event_type="share", occurred=NOW) -> EngagementEvent:
    row = EngagementEvent(
        user_id=user.id,
        session_id=uuid.uuid4(),
        story_id=story.id,
        event_type=event_type,
        occurred_at=occurred,
        ingested_at=occurred,
    )
    db.add(row)
    db.commit()
    return row


def stored_user_tags(db, user) -> dict[uuid.UUID, UserTag]:
    """What is really in the database, not what the session remembers."""
    db.commit()
    db.expire_all()
    return {row.tag_id: row for row in db.scalars(select(UserTag).where(UserTag.user_id == user.id))}


def stored_reactions(db, user) -> list[StoryReaction]:
    db.commit()
    db.expire_all()
    return list(db.scalars(select(StoryReaction).where(StoryReaction.user_id == user.id)))


def affinity_updated_at(db, user) -> datetime | None:
    db.commit()
    db.expire_all()
    return db.get(User, user.id).affinity_updated_at


# ---- hourly job: reading a user's signals -----------------------------------------


def test_only_users_with_consent_are_listed(db, repo):
    yes = add_user(db, consent=True)
    add_user(db, consent=False)

    assert repo.list_consented_user_ids() == [yes.id]


def test_events_are_filtered_on_user_and_since(db, repo):
    user, other = add_user(db), add_user(db)
    story = add_story(db)
    recent = add_event(db, user, story, "share", NOW - timedelta(days=1))
    on_the_edge = add_event(db, user, story, "read_complete", SINCE)
    add_event(db, user, story, "share", SINCE - timedelta(seconds=1))
    add_event(db, other, story, "share", NOW)

    events = repo.list_events_since(user.id, SINCE)

    assert {e.id for e in events} == {recent.id, on_the_edge.id}


def test_events_come_back_with_their_fields(db, repo):
    user = add_user(db)
    story = add_story(db)
    stored = add_event(db, user, story, "read_complete", NOW)

    [event] = repo.list_events_since(user.id, SINCE)

    assert event.user_id == user.id
    assert event.story_id == story.id
    assert event.event_type == "read_complete"
    assert naive(event.occurred_at) == naive(stored.occurred_at)


def test_reactions_are_filtered_on_user_and_since(db, repo):
    user, other = add_user(db), add_user(db)
    new, edge, old = add_story(db), add_story(db), add_story(db)
    db.add_all([
        StoryReaction(user_id=user.id, story_id=new.id, reaction="like", updated_at=NOW),
        StoryReaction(user_id=user.id, story_id=edge.id, reaction="dislike", updated_at=SINCE),
        StoryReaction(user_id=user.id, story_id=old.id, reaction="like", updated_at=SINCE - timedelta(seconds=1)),
        StoryReaction(user_id=other.id, story_id=new.id, reaction="like", updated_at=NOW),
    ])
    db.commit()

    reactions = {r.story_id: r.reaction for r in repo.list_reactions_since(user.id, SINCE)}

    assert reactions == {new.id: Reaction.like, edge.id: Reaction.dislike}


def test_only_declared_tags_are_listed_with_when_they_were_declared(db, repo):
    user, other = add_user(db), add_user(db)
    sport, music, tech = add_tag(db, "sport"), add_tag(db, "music"), add_tag(db, "tech")
    declared_at = NOW - timedelta(days=3)
    add_user_tag(db, user, sport, declared=True, updated_at=declared_at)
    add_user_tag(db, user, music, declared=False, score=4.0, computed_at=NOW)
    add_user_tag(db, other, tech, declared=True)

    [declared] = repo.list_declared_tags(user.id)

    assert declared.tag_id == sport.id
    assert naive(declared.declared_at) == naive(declared_at)


# ---- hourly job: saving the result --------------------------------------------------


def test_new_scores_are_stored_as_scored_tags(db, repo):
    user = add_user(db)
    sport, music = add_tag(db, "sport"), add_tag(db, "music")

    repo.replace_tag_scores(user.id, {sport.id: 7.5, music.id: -2.0}, NOW)

    rows = stored_user_tags(db, user)
    assert {tag_id: row.score for tag_id, row in rows.items()} == {sport.id: 7.5, music.id: -2.0}
    assert all(row.is_declared is False for row in rows.values())
    assert all(naive(row.computed_at) == naive(NOW) for row in rows.values())


def test_storing_scores_marks_when_the_user_was_scored(db, repo):
    user = add_user(db)
    sport = add_tag(db, "sport")

    repo.replace_tag_scores(user.id, {sport.id: 1.0}, NOW)

    assert naive(affinity_updated_at(db, user)) == naive(NOW)


def test_replacing_updates_kept_scores_and_drops_scores_that_are_gone(db, repo):
    user = add_user(db)
    kept, gone, new = add_tag(db, "kept"), add_tag(db, "gone"), add_tag(db, "new")
    earlier = NOW - timedelta(hours=1)
    add_user_tag(db, user, kept, declared=False, score=3.0, computed_at=earlier)
    add_user_tag(db, user, gone, declared=False, score=9.0, computed_at=earlier)

    repo.replace_tag_scores(user.id, {kept.id: 4.0, new.id: 2.0}, NOW)

    rows = stored_user_tags(db, user)
    assert {tag_id: row.score for tag_id, row in rows.items()} == {kept.id: 4.0, new.id: 2.0}
    assert naive(rows[kept.id].computed_at) == naive(NOW)


def test_a_declared_tag_without_a_new_score_stays_with_score_zero(db, repo):
    user = add_user(db)
    sport = add_tag(db, "sport")
    add_user_tag(db, user, sport, declared=True, score=6.0, computed_at=NOW - timedelta(hours=1))

    repo.replace_tag_scores(user.id, {}, NOW)

    row = stored_user_tags(db, user)[sport.id]
    assert row.is_declared is True
    assert row.score == 0.0
    assert naive(row.computed_at) == naive(NOW)


def test_scoring_a_declared_tag_keeps_it_declared_and_keeps_its_declare_date(db, repo):
    # The declared-tag bonus fades from updated_at, so scoring must not move it.
    user = add_user(db)
    sport = add_tag(db, "sport")
    declared_at = NOW - timedelta(days=10)
    add_user_tag(db, user, sport, declared=True, updated_at=declared_at)

    repo.replace_tag_scores(user.id, {sport.id: 5.0}, NOW)

    row = stored_user_tags(db, user)[sport.id]
    assert row.is_declared is True
    assert row.score == 5.0
    assert naive(row.updated_at) == naive(declared_at)


def test_replacing_scores_leaves_other_users_alone(db, repo):
    user, other = add_user(db), add_user(db)
    sport = add_tag(db, "sport")
    add_user_tag(db, other, sport, declared=False, score=8.0, computed_at=NOW - timedelta(hours=1))

    repo.replace_tag_scores(user.id, {}, NOW)

    assert stored_user_tags(db, other)[sport.id].score == 8.0


def test_scores_of_users_without_consent_are_cleared(db, repo):
    gave_up = add_user(db, consent=False, scored_at=NOW)
    sport, music = add_tag(db, "sport"), add_tag(db, "music")
    add_user_tag(db, gave_up, sport, declared=True, score=6.0, computed_at=NOW)
    add_user_tag(db, gave_up, music, declared=False, score=3.0, computed_at=NOW)

    repo.delete_tag_scores_without_consent()

    rows = stored_user_tags(db, gave_up)
    assert list(rows) == [sport.id]  # the scored-only row is gone
    assert rows[sport.id].score == 0.0
    assert rows[sport.id].computed_at is None
    assert affinity_updated_at(db, gave_up) is None


def test_clearing_scores_without_consent_leaves_users_with_consent_alone(db, repo):
    keeps = add_user(db, consent=True, scored_at=NOW)
    music = add_tag(db, "music")
    add_user_tag(db, keeps, music, declared=False, score=3.0, computed_at=NOW)

    repo.delete_tag_scores_without_consent()

    assert stored_user_tags(db, keeps)[music.id].score == 3.0
    assert naive(affinity_updated_at(db, keeps)) == naive(NOW)


# ---- reactions ----------------------------------------------------------------------


def test_a_reaction_is_stored(db, repo):
    user = add_user(db)
    story = add_story(db)

    result = repo.set_reaction(user.id, story.id, Reaction.like, NOW)

    assert result.reaction is Reaction.like
    [row] = stored_reactions(db, user)
    assert (row.story_id, row.reaction) == (story.id, "like")


def test_a_new_reaction_on_the_same_story_replaces_the_old_one(db, repo):
    user = add_user(db)
    story = add_story(db)
    later = NOW + timedelta(minutes=5)
    repo.set_reaction(user.id, story.id, Reaction.like, NOW)

    repo.set_reaction(user.id, story.id, Reaction.dislike, later)

    [row] = stored_reactions(db, user)
    assert row.reaction == "dislike"
    assert naive(row.updated_at) == naive(later)


def test_a_reaction_can_be_removed(db, repo):
    user = add_user(db)
    story = add_story(db)
    repo.set_reaction(user.id, story.id, Reaction.like, NOW)

    repo.delete_reaction(user.id, story.id)

    assert stored_reactions(db, user) == []


def test_removing_a_reaction_that_does_not_exist_is_fine(db, repo):
    user = add_user(db)
    story = add_story(db)

    repo.delete_reaction(user.id, story.id)

    assert stored_reactions(db, user) == []


# ---- consent withdrawn ----------------------------------------------------------------


def test_withdrawing_consent_removes_reactions_and_scores(db, repo):
    user = add_user(db, scored_at=NOW)
    story = add_story(db)
    sport, music = add_tag(db, "sport"), add_tag(db, "music")
    repo.set_reaction(user.id, story.id, Reaction.like, NOW)
    add_user_tag(db, user, sport, declared=True, score=6.0, computed_at=NOW)
    add_user_tag(db, user, music, declared=False, score=3.0, computed_at=NOW)

    repo.delete_algorithm_data(user.id)

    assert stored_reactions(db, user) == []
    rows = stored_user_tags(db, user)
    assert list(rows) == [sport.id]  # declared interest stays, its score doesn't
    assert (rows[sport.id].score, rows[sport.id].computed_at) == (0.0, None)
    assert affinity_updated_at(db, user) is None


def test_withdrawing_consent_leaves_other_users_alone(db, repo):
    user, other = add_user(db), add_user(db, scored_at=NOW)
    story = add_story(db)
    music = add_tag(db, "music")
    repo.set_reaction(other.id, story.id, Reaction.like, NOW)
    add_user_tag(db, other, music, declared=False, score=3.0, computed_at=NOW)

    repo.delete_algorithm_data(user.id)

    assert len(stored_reactions(db, other)) == 1
    assert stored_user_tags(db, other)[music.id].score == 3.0
    assert naive(affinity_updated_at(db, other)) == naive(NOW)


# ---- feed request ----------------------------------------------------------------------


def test_stored_scores_can_be_read_back(db, repo):
    user = add_user(db)
    sport, music = add_tag(db, "sport"), add_tag(db, "music")
    repo.replace_tag_scores(user.id, {sport.id: 7.5, music.id: -2.0}, NOW)
    db.commit()

    assert repo.get_tag_scores(user.id) == {sport.id: 7.5, music.id: -2.0}


def test_a_declared_tag_that_was_never_scored_has_no_score_yet(db, repo):
    user = add_user(db)
    sport = add_tag(db, "sport")
    add_user_tag(db, user, sport, declared=True, computed_at=None)

    assert repo.get_tag_scores(user.id) == {}


def test_a_user_without_scores_gets_an_empty_result(db, repo):
    user = add_user(db)

    assert repo.get_tag_scores(user.id) == {}


def test_only_recent_published_stories_are_candidates(db, repo):
    fresh = add_story(db, StoryStatus.published, NOW)
    edge = add_story(db, StoryStatus.published, SINCE)
    add_story(db, StoryStatus.published, SINCE - timedelta(seconds=1))
    add_story(db, StoryStatus.draft, NOW)
    add_story(db, StoryStatus.archived, NOW)

    candidates = repo.list_candidate_stories(SINCE)

    assert {story.id for story in candidates} == {fresh.id, edge.id}


# ---- both -----------------------------------------------------------------------------


def test_story_tags_are_grouped_per_story(db, repo):
    sport, music = add_tag(db, "sport"), add_tag(db, "music")
    both = add_story(db, tags=[sport, music])
    one = add_story(db, tags=[music])
    not_asked = add_story(db, tags=[sport])

    result = repo.get_story_tags([both.id, one.id])

    assert {story_id: set(tags) for story_id, tags in result.items()} == {
        both.id: {sport.id, music.id},
        one.id: {music.id},
    }
    assert not_asked.id not in result


def test_a_story_without_tags_may_be_missing(db, repo):
    untagged = add_story(db)

    assert repo.get_story_tags([untagged.id]).get(untagged.id, []) == []


def test_no_story_ids_means_no_query_and_no_tags(repo):
    assert repo.get_story_tags([]) == {}
