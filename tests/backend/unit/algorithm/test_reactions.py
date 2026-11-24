"""current_reactions(): a story's like or dislike, read from engagement events."""

from dataclasses import replace
from datetime import timedelta

from Backend.Logic.Algorithm.reactions import current_reactions
from Backend.Logic.domain.story_reaction import Reaction
from tests.backend.unit.algorithm.builders import days_ago, make_event, new_id

USER = new_id()


def reactions_of(events):
    return {r.story_id: r.reaction for r in current_reactions(events)}


def test_like_and_dislike_events_are_reactions():
    liked, disliked = new_id(), new_id()

    assert reactions_of([
        make_event(USER, liked, "like"),
        make_event(USER, disliked, "dislike"),
    ]) == {liked: Reaction.like, disliked: Reaction.dislike}


def test_the_latest_tap_wins_whatever_order_the_events_come_in():
    story = new_id()
    newest = make_event(USER, story, "dislike", happened_days_ago=1)
    oldest = make_event(USER, story, "like", happened_days_ago=2)

    assert reactions_of([newest, oldest]) == {story: Reaction.dislike}


def test_reaction_removed_undoes_the_reaction():
    story = new_id()

    assert reactions_of([
        make_event(USER, story, "like", happened_days_ago=1),
        make_event(USER, story, "reaction_removed"),
    ]) == {}


def test_liking_again_after_undoing_is_a_like():
    story = new_id()

    assert reactions_of([
        make_event(USER, story, "like", happened_days_ago=2),
        make_event(USER, story, "reaction_removed", happened_days_ago=1),
        make_event(USER, story, "like"),
    ]) == {story: Reaction.like}


def test_the_reaction_dates_from_the_latest_tap():
    story = new_id()
    [reaction] = current_reactions([
        make_event(USER, story, "like", happened_days_ago=5),
        make_event(USER, story, "like", happened_days_ago=1),
    ])

    assert reaction.updated_at == days_ago(1)
    assert reaction.user_id == USER


def test_same_timestamp_the_one_stored_last_wins():
    story = new_id()
    first = make_event(USER, story, "like")
    second = replace(
        make_event(USER, story, "dislike"),
        ingested_at=first.ingested_at + timedelta(seconds=1),
    )

    assert reactions_of([second, first]) == {story: Reaction.dislike}


def test_other_events_are_not_reactions():
    story = new_id()

    assert reactions_of([
        make_event(USER, story, "share"),
        make_event(USER, story, "read_complete"),
    ]) == {}


def test_a_share_after_a_like_keeps_the_like():
    story = new_id()

    assert reactions_of([
        make_event(USER, story, "like", happened_days_ago=1),
        make_event(USER, story, "share"),
    ]) == {story: Reaction.like}


def test_events_without_a_story_are_skipped():
    assert current_reactions([make_event(USER, None, "like")]) == []
