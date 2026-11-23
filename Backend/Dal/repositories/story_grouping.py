"""Assign unlinked Dutch coverage to stories in the caller's transaction."""

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import selectinload

from Backend.Dal.models import Article, Story, StoryArticle, StoryStatus
from Backend.Logic.story_grouping import (
    GROUPING_TIMEZONE,
    article_day,
    assess_story,
    cosine,
    exclusion_reason,
    ranked_representatives,
    representative,
)

DUTCH_CODES = ("nl", "nl-nl", "nl-be", "nld", "dut")


def _validate_arguments(limit, publication_day):
    if publication_day is not None and (
        not isinstance(publication_day, date) or isinstance(publication_day, datetime)
    ):
        raise ValueError("publication_day must be a date")

    if limit is None and publication_day is None:
        raise ValueError("Unlimited grouping requires a publication day")

    if limit is not None and (
        not isinstance(limit, int) or isinstance(limit, bool) or limit < 1
    ):
        raise ValueError("limit must be a positive integer")


def _acquire_grouping_lock(db):
    """Serialize overlapping grouping jobs on PostgreSQL."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(827461305)"))


def _build_article_query(limit, publication_day):
    event_time = func.coalesce(Article.published_at, Article.first_seen_at)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    language = func.lower(Article.language)

    dutch = or_(
        Article.language.is_(None),
        language.in_(DUTCH_CODES),
    )

    complete_text = [
        func.trim(
            func.replace(
                func.replace(func.replace(column, "\n", ""), "\r", ""),
                "\t",
                "",
            )
        )
        != ""
        for column in (Article.title, Article.description, Article.content)
    ]

    period = event_time >= cutoff

    if publication_day is not None:
        start = datetime.combine(
            publication_day, time.min, GROUPING_TIMEZONE
        ).astimezone(timezone.utc)
        end = datetime.combine(
            publication_day + timedelta(days=1),
            time.min,
            GROUPING_TIMEZONE,
        ).astimezone(timezone.utc)

        period = (Article.published_at >= start) & (Article.published_at < end)

    query = (
        select(Article)
        .where(~Article.stories.any(), dutch, period, *complete_text)
        .order_by(Article.first_seen_at, Article.id)
    )

    if limit is not None:
        query = query.limit(limit)

    return query, event_time, period, cutoff


def _build_report(pending_count, assigned, excluded, stories):
    return {
        "eligible_unlinked_articles": pending_count,
        "assigned_articles": assigned,
        "excluded_articles": excluded,
        "stories": stories,
    }


def _handle_empty_result(review, report):
    if review:
        review({}, {}, set(), {})

    if report:
        report(_build_report(0, 0, {}, []))


def _load_existing_groups(
    db,
    period,
    publication_day,
    event_time,
):
    recent_member = StoryArticle.article.has(
        period
        if publication_day is not None
        else event_time >= datetime.now(timezone.utc) - timedelta(days=31)
    )

    stories = db.scalars(
        select(Story)
        .where(
            Story.status != StoryStatus.archived,
            Story.articles.any(recent_member),
        )
        .options(selectinload(Story.articles))
    ).all()

    groups = {}
    story_by_id = {}
    documents = {}

    for story in stories:
        primary = next(
            (link.article for link in story.articles if link.is_primary),
            None,
        )
        members = [link.article for link in story.articles]

        if primary is None:
            continue

        if any(
            (member.language or "nl").lower() not in DUTCH_CODES for member in members
        ):
            continue

        if publication_day is not None and any(
            article_day(member) != publication_day for member in members
        ):
            continue

        groups[story.id] = (primary, members)
        story_by_id[story.id] = story
        documents.update((member.id, member) for member in members)

    return groups, story_by_id, documents


def _assign_pending_articles(
    db,
    pending,
    groups,
    story_by_id,
    vectors,
):
    touched = set()
    assigned = 0
    decisions = {}
    excluded = {}
    created = set()

    for article in pending:
        if len(vectors[article.id]) < 3:
            excluded[str(article.id)] = (
                exclusion_reason(article) or "insufficient usable text"
            )
            continue

        decision = assess_story(article, groups, vectors)
        decisions[article.id] = decision["reason"]

        story_id = (
            decision["scores"][0][1] if decision["reason"] == "accepted" else None
        )

        if story_id is None:
            story = Story(title=article.title)
            db.add(story)
            db.flush()

            story_by_id[story.id] = story
            created.add(story.id)
            groups[story.id] = (article, [])
        else:
            story = story_by_id[story_id]

        members = groups[story.id][1]
        members.append(article)

        groups[story.id] = (
            representative(members, vectors),
            members,
        )

        story.articles.append(StoryArticle(article=article))
        touched.add(story.id)
        assigned += 1

    return touched, assigned, decisions, excluded, created


def _select_story_image(primary, members, vectors):
    candidates = [primary] + [
        member
        for member in ranked_representatives(members, vectors)
        if member.id != primary.id
    ]

    return next(
        (
            member.img_url.strip()
            for member in candidates
            if member.img_url and member.img_url.strip()
        ),
        None,
    )


def _update_touched_stories(
    story_by_id,
    groups,
    touched,
    vectors,
):
    now = datetime.now(timezone.utc)

    for story_id in touched:
        story = story_by_id[story_id]
        primary, members = groups[story_id]

        story.title = primary.title
        story.context = primary.content
        story.img_url = _select_story_image(primary, members, vectors)
        story.status = StoryStatus.published

        if story.first_published_at is None:
            story.first_published_at = now

        story.last_updated_at = now

        for link in story.articles:
            is_primary = link.article.id == primary.id
            link.is_primary = is_primary
            link.similarity_score = (
                1
                if is_primary
                else round(
                    cosine(
                        vectors[primary.id],
                        vectors[link.article.id],
                    ),
                    6,
                )
            )


def _build_story_report(
    touched,
    created,
    groups,
    story_by_id,
):
    return [
        {
            "id": str(key),
            "created": key in created,
            "primary_article_id": str(groups[key][0].id),
            "article_ids": [str(article.id) for article in groups[key][1]],
            "title": story_by_id[key].title,
            "context": story_by_id[key].context,
            "img_url": story_by_id[key].img_url,
            "status": story_by_id[key].status.value,
            "first_published_at": (story_by_id[key].first_published_at.isoformat()),
        }
        for key in sorted(touched, key=str)
    ]


def group_articles(
    db,
    *,
    review=None,
    limit=500,
    publication_day=None,
    report=None,
):
    """Process complete, unlinked articles in ingestion order."""
    _validate_arguments(limit, publication_day)
    _acquire_grouping_lock(db)

    query, event_time, period, _cutoff = _build_article_query(
        limit,
        publication_day,
    )

    pending = db.scalars(query).all()

    if not pending:
        _handle_empty_result(review, report)
        return 0

    groups, story_by_id, documents = _load_existing_groups(
        db,
        period,
        publication_day,
        event_time,
    )

    documents.update((article.id, article) for article in pending)

    from Backend.Logic.story_grouping import vectors_for

    vectors = vectors_for(documents.values())

    touched, assigned, decisions, excluded, created = _assign_pending_articles(
        db,
        pending,
        groups,
        story_by_id,
        vectors,
    )

    _update_touched_stories(
        story_by_id,
        groups,
        touched,
        vectors,
    )

    db.flush()

    if review:
        review(groups, vectors, touched, decisions)

    if report:
        report(
            _build_report(
                len(pending),
                assigned,
                excluded,
                _build_story_report(
                    touched,
                    created,
                    groups,
                    story_by_id,
                ),
            )
        )

    return assigned
