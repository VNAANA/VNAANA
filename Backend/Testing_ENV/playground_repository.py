"""The playground's own in-memory world, with a clock you can move.

Holds the mock articles, one user and everything that user did. The real
AlgorithmService reads it through the same ports the API uses, so the
algorithm that runs here is exactly the algorithm the API runs.

How the clock works:
- everything the user does goes into one action log, stamped with the clock
- the algorithm only sees what happened at or before the clock
- moving the clock back hides later actions, moving it forward shows them again
- doing something new while later actions are hidden throws those away,
  like undo in an editor: there is only ever one history
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from Backend.Logic.Algorithm.shared_types import StoryTags, TagScores
from Backend.Logic.domain.declared_tag import DeclaredTag
from Backend.Logic.domain.engagement_event import EngagementEvent
from Backend.Logic.domain.story import Story, StoryStatus
from Backend.Logic.domain.story_reaction import Reaction, StoryReaction
from Backend.Logic.domain.user import User
from Backend.Testing_ENV.mock_data import ARTICLES, TAGS, MockArticle

# A fixed start date, so the demo looks the same every time it runs.
START = datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc)

# The last articles appear on day 18 and expire 30 days later, so by day 50
# everything has faded out and the end of the story can be shown too.
LAST_DAY = 50


class ActionKind(str, enum.Enum):
    declare = "declare"                # a tag picked during onboarding
    like = "like"
    dislike = "dislike"
    clear_reaction = "clear_reaction"  # unlike / undislike
    share = "share"
    read = "read"


REACTION_KINDS = {ActionKind.like, ActionKind.dislike, ActionKind.clear_reaction}

# Actions that are stored as engagement events, with the event_type the API uses.
EVENT_TYPES = {
    ActionKind.share: "share",
    ActionKind.read: "read_complete",
}


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    at: datetime
    story_id: uuid.UUID | None = None
    tag_id: uuid.UUID | None = None


class NoConsentError(Exception):
    """Without consent nothing the user does is tracked, same as in the API."""


class World:
    def __init__(self) -> None:
        self.tag_ids: dict[str, uuid.UUID] = {name: uuid.uuid4() for name in TAGS}
        self.tag_names: dict[uuid.UUID, str] = {tag_id: name for name, tag_id in self.tag_ids.items()}

        self.stories: list[Story] = []
        self.story_tags: StoryTags = {}
        self.articles: dict[uuid.UUID, MockArticle] = {}

        for article in ARTICLES:
            published_at = START + timedelta(days=article.published_day)
            story = Story(
                id=uuid.uuid4(),
                title=article.title,
                summary=article.summary,
                context=None,
                status=StoryStatus.published,
                first_published_at=published_at,
                last_updated_at=published_at,
            )
            self.stories.append(story)
            self.story_tags[story.id] = [self.tag_ids[name] for name in article.tags]
            self.articles[story.id] = article

        self.user: User | None = None
        self.session_id = uuid.uuid4()
        self.day = 0
        self.actions: list[Action] = []
        self.stored_scores: TagScores = {}

    # ---- the clock ---------------------------------------------------------------

    @property
    def now(self) -> datetime:
        return START + timedelta(days=self.day)

    def set_day(self, day: int) -> None:
        self.day = max(0, min(LAST_DAY, day))

    # ---- what the user does ------------------------------------------------------

    def onboard(self, tag_names: list[str], *, consent: bool) -> None:
        """Start over with a new user who picked these tags on day 0."""
        self.user = User(
            id=uuid.uuid4(),
            language="en",
            preferences=None,
            analytics_consent=consent,
            consent_updated_at=START,
            auth_provider="playground",
            auth_subject="playground-user",
            affinity_updated_at=None,
        )
        self.day = 0
        self.stored_scores = {}

        # Declared tags are saved even without consent: the user typed them in
        # themselves. Without consent the algorithm just never reads them.
        self.actions = [
            Action(ActionKind.declare, START, tag_id=self.tag_ids[name])
            for name in tag_names
        ]

    def record(self, kind: ActionKind, story_id: uuid.UUID) -> None:
        """The user does something with an article, at the current clock."""
        if self.user is None or not self.user.analytics_consent:
            raise NoConsentError()

        # Undo semantics: a new action in the past ends the hidden future.
        self.actions = self.visible_actions()
        self.actions.append(Action(kind, self.now, story_id=story_id))

    # ---- reading the log ---------------------------------------------------------

    def visible_actions(self) -> list[Action]:
        """What happened at or before the clock: all the algorithm may see."""
        return [action for action in self.actions if action.at <= self.now]

    def hidden_actions(self) -> list[Action]:
        """What happened after the clock: undone for now, back when moving forward."""
        return [action for action in self.actions if action.at > self.now]

    def reaction_on(self, story_id: uuid.UUID) -> StoryReaction | None:
        """The user's current like/dislike on a story; the latest tap wins."""
        latest = None

        for action in self.visible_actions():
            if action.story_id == story_id and action.kind in REACTION_KINDS:
                latest = action

        if latest is None or latest.kind == ActionKind.clear_reaction:
            return None

        return StoryReaction(
            user_id=self.user.id,
            story_id=story_id,
            reaction=Reaction(latest.kind.value),
            updated_at=latest.at,
        )

    def published_stories(self) -> list[Story]:
        return [story for story in self.stories if story.last_updated_at <= self.now]

    def tag_names_of(self, story_id: uuid.UUID) -> list[str]:
        return [self.tag_names[tag_id] for tag_id in self.story_tags[story_id]]


class PlaygroundAlgorithmRepository:
    """Implements Backend.Logic.ports.algorithm_repository.AlgorithmRepository."""

    def __init__(self, world: World) -> None:
        self.world = world

    def _is_user(self, user_id: uuid.UUID) -> bool:
        return self.world.user is not None and self.world.user.id == user_id

    # ---- the hourly job: reading signals -------------------------------------------

    def list_consented_user_ids(self) -> list[uuid.UUID]:
        user = self.world.user
        return [user.id] if user is not None and user.analytics_consent else []

    def list_events_since(self, user_id: uuid.UUID, since: datetime) -> list[EngagementEvent]:
        if not self._is_user(user_id):
            return []

        return [
            EngagementEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                session_id=self.world.session_id,
                story_id=action.story_id,
                article_id=None,
                event_type=EVENT_TYPES[action.kind],
                occurred_at=action.at,
                ingested_at=action.at,
                active_duration_ms=None,
                event_metadata=None,
            )
            for action in self.world.visible_actions()
            if action.kind in EVENT_TYPES and action.at >= since
        ]

    def list_reactions_since(self, user_id: uuid.UUID, since: datetime) -> list[StoryReaction]:
        if not self._is_user(user_id):
            return []

        reactions = (self.world.reaction_on(story.id) for story in self.world.stories)
        return [reaction for reaction in reactions if reaction is not None and reaction.updated_at >= since]

    def list_declared_tags(self, user_id: uuid.UUID) -> list[DeclaredTag]:
        if not self._is_user(user_id):
            return []

        return [
            DeclaredTag(tag_id=action.tag_id, declared_at=action.at)
            for action in self.world.visible_actions()
            if action.kind == ActionKind.declare
        ]

    # ---- the hourly job: saving the result -------------------------------------------

    def replace_tag_scores(self, user_id: uuid.UUID, scores: TagScores, computed_at: datetime) -> None:
        if self._is_user(user_id):
            self.world.stored_scores = dict(scores)

    def delete_tag_scores_without_consent(self) -> None:
        user = self.world.user
        if user is not None and not user.analytics_consent:
            self.world.stored_scores = {}

    # ---- reactions ---------------------------------------------------------------------

    def set_reaction(
        self, user_id: uuid.UUID, story_id: uuid.UUID, reaction: Reaction, at: datetime
    ) -> StoryReaction:
        # The playground's clock decides the time, so `at` is not used here.
        self.world.record(ActionKind(reaction.value), story_id)
        return self.world.reaction_on(story_id)

    def delete_reaction(self, user_id: uuid.UUID, story_id: uuid.UUID) -> None:
        if self.world.reaction_on(story_id) is not None:
            self.world.record(ActionKind.clear_reaction, story_id)

    def delete_algorithm_data(self, user_id: uuid.UUID) -> None:
        if not self._is_user(user_id):
            return

        self.world.actions = [action for action in self.world.actions if action.kind not in REACTION_KINDS]
        self.world.stored_scores = {}

    # ---- the feed ----------------------------------------------------------------------

    def get_tag_scores(self, user_id: uuid.UUID) -> TagScores:
        return dict(self.world.stored_scores) if self._is_user(user_id) else {}

    def list_candidate_stories(self, since: datetime) -> list[Story]:
        return [story for story in self.world.published_stories() if story.last_updated_at >= since]

    def get_story_tags(self, story_ids: list[uuid.UUID]) -> StoryTags:
        return {
            story_id: list(self.world.story_tags[story_id])
            for story_id in story_ids
            if story_id in self.world.story_tags
        }


class PlaygroundUserRepository:
    """The part of Backend.Logic.ports.user_repository.UserRepository that
    AlgorithmService uses: looking up the one playground user."""

    def __init__(self, world: World) -> None:
        self.world = world

    def get(self, user_id: uuid.UUID) -> User | None:
        user = self.world.user
        return user if user is not None and user.id == user_id else None
