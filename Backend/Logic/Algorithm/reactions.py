"""Likes and dislikes, read from the engagement events.

The app does not store a reaction in story_reactions. Every tap is an
engagement event instead:

- `like`             the heart
- `dislike`          "Not interested"
- `reaction_removed` tapping the same button again to undo it

A story's current reaction is the latest of these events for that story.
Earlier taps are kept as history but count for nothing, so tapping like
ten times is still one like.
"""

import uuid

from Backend.Logic.domain.engagement_event import EngagementEvent
from Backend.Logic.domain.story_reaction import Reaction, StoryReaction

REACTION_EVENTS: dict[str, Reaction | None] = {
    "like": Reaction.like,
    "dislike": Reaction.dislike,
    "reaction_removed": None,
}


def current_reactions(events: list[EngagementEvent]) -> list[StoryReaction]:
    """Each story's latest like or dislike, as of when it was tapped.

    Other event types are skipped. A story whose latest reaction event is
    `reaction_removed` has no reaction.
    """
    reaction_events = [
        event
        for event in events
        if event.event_type in REACTION_EVENTS
        and event.story_id is not None
        and event.user_id is not None
    ]
    # Oldest first, so a later tap overwrites an earlier one. ingested_at
    # breaks a tie between two taps sent with the same timestamp.
    reaction_events.sort(key=lambda event: (event.occurred_at, event.ingested_at))

    latest: dict[uuid.UUID, EngagementEvent] = {}
    for event in reaction_events:
        latest[event.story_id] = event

    return [
        StoryReaction(
            user_id=event.user_id,
            story_id=event.story_id,
            reaction=reaction,
            updated_at=event.occurred_at,
        )
        for event in latest.values()
        if (reaction := REACTION_EVENTS[event.event_type]) is not None
    ]
