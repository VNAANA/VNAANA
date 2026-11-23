from Backend.Logic.domain.feed import FeedStatus
from Backend.Presentation.schemas.common import ORMModel
from Backend.Presentation.schemas.stories import StoryCardRead


class RankedStoryRead(ORMModel):
    story: StoryCardRead
    score: float


class FeedRead(ORMModel):
    """The "For you" answer.

    status tells the frontend what to show:
    - available      → show `stories`
    - not_logged_in  → general feed, maybe a "log in for a personal feed" hint
    - no_consent     → general feed, "turn on consent to get a personal feed"
    - locked         → general feed, "read a few more stories to unlock this"
    """

    status: FeedStatus
    stories: list[RankedStoryRead]
