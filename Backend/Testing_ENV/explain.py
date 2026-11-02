"""Everything the playground says to explain the algorithm.

Two kinds of explanation:
- fixed texts for the "How it works" button and the "?" icons. They are
  built from the real constants (weights, thresholds, days), so changing a
  weight in the algorithm changes the explanation with it.
- live breakdowns: why an article has its score, and which actions built a
  tag score. They use the real algorithm functions, so the numbers shown
  are always the numbers the algorithm used.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from Backend.Logic.Algorithm.decay import LIFETIME_DAYS, SECONDS_PER_DAY, as_utc, decay
from Backend.Logic.Algorithm.ranking import (
    BROAD_MIN_SCORE,
    BROAD_TAG_COUNT,
    FOCUSED_MIN_SCORE,
    final_score,
    story_score,
)
from Backend.Logic.Algorithm.scoring import DECLARED_TAG_BONUS, EVENT_WEIGHTS, REACTION_WEIGHTS
from Backend.Logic.Algorithm.shared_types import TagScores
from Backend.Logic.domain.story_reaction import Reaction
from Backend.Testing_ENV.playground_repository import EVENT_TYPES, START, ActionKind, World

LIKE = REACTION_WEIGHTS[Reaction.like]
DISLIKE = REACTION_WEIGHTS[Reaction.dislike]
SHARE = EVENT_WEIGHTS[EVENT_TYPES[ActionKind.share]]
READ = EVENT_WEIGHTS[EVENT_TYPES[ActionKind.read]]


def points(value: float) -> str:
    """+5, -5, +1.67: always with a sign, at most two decimals."""
    text = f"{value:+.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("+0", "-0") else text


def number(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def age_in_days(moment: datetime, now: datetime) -> float:
    return (as_utc(now) - as_utc(moment)).total_seconds() / SECONDS_PER_DAY


def day_of(moment: datetime) -> int:
    """Which day of the simulation a moment falls on."""
    return round(age_in_days(START, moment))


# ---- the "How it works" button ------------------------------------------------------

HOW_IT_WORKS = f"""\
The "For you" feed is built in four steps.

1. You do things
Every action says something about what you like:
   Like {points(LIKE)}    Dislike {points(DISLIKE)}    Share {points(SHARE)}    Read to the end {points(READ)}
Each interest you pick during onboarding also gives that tag {points(DECLARED_TAG_BONUS)}.

2. Actions become tag scores
Articles have tags, like Sports or Politics. An action gives its full points
to every tag of that article. Liking an article about Sports and Climate
gives both Sports and Climate {points(LIKE)}.
Points fade: today they count fully, after {LIFETIME_DAYS // 2} days half, after
{LIFETIME_DAYS} days not at all. What you liked a month ago says less about you
than what you liked today.

3. Tag scores become an article score
An article's score is the average of your scores for its tags. A tag you
have never interacted with counts as 0.
Newer articles get priority: a positive score fades with the article's age
in the same way, over {LIFETIME_DAYS} days. A negative score stays as it is,
otherwise articles you dislike would slowly climb back up as they get older.

4. The feed
Articles are sorted from highest to lowest score. When two are equal, the
newest goes first. Articles older than {LIFETIME_DAYS} days are removed.

Privacy: none of this happens without your consent. Without it, nothing you
do is stored and everyone sees the same general feed.

Click any "?" in the playground for the details, with your own numbers.
"""


# ---- the "?" icons --------------------------------------------------------------------

HELP: dict[str, tuple[str, str]] = {
    "consent": (
        "Consent",
        "Personalisation only works if you allow us to track what you do.\n\n"
        "With consent: likes, shares and reads are stored and used to build "
        "your \"For you\" feed.\n\n"
        "Without consent: nothing you do is stored, the algorithm never runs "
        "for you, and you see the same general feed as everyone else. The "
        "interests you pick are kept, but the algorithm doesn't use them.\n\n"
        "Consent is off by default and can be turned off at any time. "
        "Turning it off deletes your likes, dislikes and scores.",
    ),
    "interests": (
        "Picking your interests",
        f"Every interest you pick gives that tag {points(DECLARED_TAG_BONUS)} "
        "to start with.\n\n"
        "This gives the algorithm something to work with before you have done "
        "anything, so your \"For you\" feed is unlocked straight away.\n\n"
        f"Like every other signal, the bonus fades: to 0 after {LIFETIME_DAYS} "
        "days. From then on your feed is based on what you actually do, not on "
        "what you said at the start.",
    ),
    "feed_status": (
        "When is \"For you\" unlocked?",
        "The feed is only personalised once the algorithm knows enough about "
        "you. That is the case when one of these is true:\n\n"
        "   • you picked at least one interest during onboarding\n"
        f"   • {BROAD_TAG_COUNT} tags have a score of {BROAD_MIN_SCORE} or more "
        "(you like several things)\n"
        f"   • 1 tag has a score of {FOCUSED_MIN_SCORE} or more "
        "(you clearly like one thing)\n\n"
        "Until then you see the general feed, so the algorithm never guesses "
        "based on one or two clicks.",
    ),
    "actions": (
        "What your actions are worth",
        f"   Like {points(LIKE)}\n"
        f"   Dislike {points(DISLIKE)}\n"
        f"   Share {points(SHARE)}\n"
        f"   Read to the end {points(READ)}\n\n"
        "The points go to every tag of the article.\n\n"
        "Like and dislike are one reaction per article: the latest one counts. "
        "Disliking an article you liked replaces the like. Tapping the same "
        "button again removes the reaction.\n\n"
        "Shares and reads add up: sharing the same article twice counts twice.\n\n"
        f"A dislike ({points(DISLIKE)}) is exactly as big as the bonus for a picked "
        f"interest ({points(DECLARED_TAG_BONUS)}): one dislike cancels out an "
        "interest you picked at the start.",
    ),
    "time": (
        "Moving through time",
        "The playground has its own clock. Move it forward to see what "
        "happens to your feed over the days:\n\n"
        f"   • points fade, and are gone after {LIFETIME_DAYS} days\n"
        "   • new articles appear, and newer articles get priority\n"
        f"   • articles older than {LIFETIME_DAYS} days disappear\n\n"
        "Going back works like undo: everything you did after that day is "
        "hidden, and comes back when you move forward again. Doing something "
        "new in the past throws those later actions away for good.",
    ),
    "action_log": (
        "Action log",
        "Everything you did, with the day you did it.\n\n"
        "Greyed-out actions happened after the current day. They are undone "
        "for now and come back when you move the clock forward. If you do "
        "something new now, they are deleted.",
    ),
    "tag_scores": (
        "Your tag scores",
        "How much the algorithm thinks you like each tag, based on everything "
        f"you did in the last {LIFETIME_DAYS} days.\n\n"
        "Click a tag to see exactly which actions built its score, and how "
        "much each one has faded.",
    ),
    "article_score": (
        "Article scores",
        "The number next to each article is its score: the average of your "
        "tag scores for its tags, lowered a bit for older articles.\n\n"
        "Click an article's score to see the full calculation.",
    ),
}


# ---- live: unlock status ------------------------------------------------------------

def unlock_summary(tag_scores: TagScores, *, has_declared_tags: bool) -> str:
    broad = sum(1 for score in tag_scores.values() if score >= BROAD_MIN_SCORE)
    best = max(tag_scores.values(), default=0.0)

    return (
        f"Picked interests: {'yes' if has_declared_tags else 'no'}\n"
        f"Tags at {BROAD_MIN_SCORE} or more: {broad} of {BROAD_TAG_COUNT}\n"
        f"Highest tag score: {number(best)} of {FOCUSED_MIN_SCORE}"
    )


# ---- live: which actions built a tag score -------------------------------------------

@dataclass(frozen=True)
class Contribution:
    description: str
    day: int
    points: float
    fade: float

    @property
    def value(self) -> float:
        return self.points * self.fade


@dataclass(frozen=True)
class TagBreakdown:
    tag: str
    contributions: list[Contribution]

    @property
    def total(self) -> float:
        return sum(contribution.value for contribution in self.contributions)

    def as_text(self) -> str:
        if not self.contributions:
            return (
                f"Nothing in the last {LIFETIME_DAYS} days involved {self.tag}, "
                "so its score is 0."
            )

        lines = [
            f"Day {c.day}: {c.description}\n"
            f"      {points(c.points)} × {number(c.fade)} still counting = {points(c.value)}"
            for c in self.contributions
        ]
        lines.append(f"\nTotal: {number(self.total)}")
        lines.append(
            f"\nThe \"still counting\" part is the fading: an action counts fully on "
            f"the day itself and loses a bit every day until it reaches 0 after "
            f"{LIFETIME_DAYS} days."
        )
        return "\n".join(lines)


def tag_breakdown(world: World, tag_id: uuid.UUID) -> TagBreakdown:
    """The same signals scoring.py adds up, but with a description for each one."""
    now = world.now
    since = now - timedelta(days=LIFETIME_DAYS)
    contributions = []

    def add(description: str, weight: float, at: datetime) -> None:
        if at >= since:
            contributions.append(Contribution(description, day_of(at), weight, decay(at, now)))

    for action in world.visible_actions():
        if action.kind == ActionKind.declare and action.tag_id == tag_id:
            add("Picked during onboarding", DECLARED_TAG_BONUS, action.at)

        elif action.kind in EVENT_TYPES and tag_id in world.story_tags[action.story_id]:
            title = world.articles[action.story_id].title
            verb = "Shared" if action.kind == ActionKind.share else "Read to the end"
            add(f"{verb} \"{title}\"", EVENT_WEIGHTS[EVENT_TYPES[action.kind]], action.at)

    for story in world.stories:
        reaction = world.reaction_on(story.id)

        if reaction is not None and tag_id in world.story_tags[story.id]:
            verb = "Liked" if reaction.reaction == Reaction.like else "Disliked"
            add(f"{verb} \"{story.title}\"", REACTION_WEIGHTS[reaction.reaction], reaction.updated_at)

    contributions.sort(key=lambda contribution: contribution.day)
    return TagBreakdown(world.tag_names[tag_id], contributions)


# ---- live: why an article has its score ----------------------------------------------

@dataclass(frozen=True)
class ArticleBreakdown:
    title: str
    tag_scores: list[tuple[str, float]]
    average: float
    age_days: float
    freshness: float
    final: float

    def as_text(self) -> str:
        tags = "\n".join(f"   {name}: {number(score)}" for name, score in self.tag_scores)
        lines = [f"1. Your scores for this article's tags:\n{tags}"]

        if len(self.tag_scores) == 1:
            lines.append(f"2. Only one tag, so the article score is that tag's score: {number(self.average)}")
        else:
            sum_text = " + ".join(f"({number(s)})" if s < 0 else number(s) for _, s in self.tag_scores)
            lines.append(f"2. Average: ({sum_text}) / {len(self.tag_scores)} = {number(self.average)}")

        if self.average > 0:
            lines.append(
                f"3. Freshness: the article is {number(self.age_days)} days old, so it "
                f"still counts for {number(self.freshness)}.\n"
                f"   {number(self.average)} × {number(self.freshness)} = {number(self.final)}"
            )
        else:
            lines.append(
                "3. Freshness: not applied. The score is not positive, and an "
                "article you don't like shouldn't climb just because it is older."
            )

        lines.append(f"Final score: {number(self.final)}\n\n(Numbers are rounded to two decimals.)")
        return "\n\n".join(lines)


def article_breakdown(world: World, story_id: uuid.UUID, tag_scores: TagScores) -> ArticleBreakdown:
    story = next(story for story in world.stories if story.id == story_id)
    tag_ids = world.story_tags[story_id]
    average = story_score(tag_ids, tag_scores)

    return ArticleBreakdown(
        title=story.title,
        tag_scores=[(world.tag_names[tag_id], tag_scores.get(tag_id, 0.0)) for tag_id in tag_ids],
        average=average,
        age_days=age_in_days(story.last_updated_at, world.now),
        freshness=decay(story.last_updated_at, world.now),
        final=final_score(average, story.last_updated_at, world.now),
    )
