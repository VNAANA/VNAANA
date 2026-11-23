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
    ranked_representatives,
    representative,
    vectors_for,
)

DUTCH_CODES = ("nl", "nl-nl", "nl-be", "nld", "dut")


def group_articles(db, *, review=None, limit=500, publication_day=None, report=None):
    """Process complete, unlinked articles in ingestion order; match by publication time."""
    if publication_day is not None and (not isinstance(publication_day, date) or isinstance(publication_day, datetime)):
        raise ValueError("publication_day must be a date")
    if limit is None and publication_day is None:
        raise ValueError("Unlimited grouping requires a publication day")
    if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 1):
        raise ValueError("limit must be a positive integer")
    # Scheduled jobs can overlap. Serialize their read/assign/write sequence.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(827461305)"))
    event_time = func.coalesce(Article.published_at, Article.first_seen_at)
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    language = func.lower(Article.language)
    dutch = or_(Article.language.is_(None), language.in_(DUTCH_CODES))
    complete_text = [
        func.trim(func.replace(func.replace(func.replace(column, "\n", ""), "\r", ""), "\t", "")) != ""
        for column in (Article.title, Article.description, Article.content)
    ]
    period = event_time >= cutoff
    if publication_day is not None:
        start = datetime.combine(publication_day, time.min, GROUPING_TIMEZONE).astimezone(timezone.utc)
        end = datetime.combine(publication_day + timedelta(days=1), time.min, GROUPING_TIMEZONE).astimezone(timezone.utc)
        # Explicit day runs require a publication timestamp, not ingestion fallback.
        period = (Article.published_at >= start) & (Article.published_at < end)
    query = select(Article).where(~Article.stories.any(), dutch, period, *complete_text).order_by(Article.first_seen_at, Article.id)
    if limit is not None:
        query = query.limit(limit)
    pending = db.scalars(query).all()
    if not pending:
        if review:
            review({}, {}, set(), {})
        if report:
            report({"eligible_unlinked_articles": 0, "assigned_articles": 0, "excluded_articles": {}, "stories": []})
        return 0

    recent_member = StoryArticle.article.has(period if publication_day is not None else event_time >= cutoff - timedelta(days=1))
    stories = db.scalars(select(Story).where(
        Story.status != StoryStatus.archived, Story.articles.any(recent_member)
    ).options(selectinload(Story.articles))).all()
    groups = {}
    story_by_id = {}
    documents = {article.id: article for article in pending}
    for story in stories:
        primary = next((link.article for link in story.articles if link.is_primary), None)
        members = [link.article for link in story.articles]
        if primary is None or any((m.language or "nl").lower() not in DUTCH_CODES for m in members):
            continue
        if publication_day is not None and any(article_day(m) != publication_day for m in members):
            continue
        groups[story.id] = (primary, members)
        story_by_id[story.id] = story
        documents.update((member.id, member) for member in members)

    vectors = vectors_for(documents.values())
    touched = set()
    assigned = 0
    decisions = {}
    excluded = {}
    created = set()
    for article in pending:
        if len(vectors[article.id]) < 3:
            from Backend.Logic.story_grouping import exclusion_reason
            excluded[str(article.id)] = exclusion_reason(article) or "insufficient usable text"
            continue
        decision = assess_story(article, groups, vectors)
        decisions[article.id] = decision["reason"]
        story_id = None
        if decision["reason"] == "accepted":
            story_id = decision["scores"][0][1]
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
        groups[story.id] = (representative(members, vectors), members)
        story.articles.append(StoryArticle(article=article))
        touched.add(story.id)
        assigned += 1

    for story_id in touched:
        story = story_by_id[story_id]
        primary, members = groups[story_id]
        story.title = primary.title
        story.context = primary.content
        image_candidates = [primary] + [m for m in ranked_representatives(members, vectors) if m.id != primary.id]
        story.img_url = next((m.img_url.strip() for m in image_candidates if m.img_url and m.img_url.strip()), None)
        now = datetime.now(timezone.utc)
        story.status = StoryStatus.published
        if story.first_published_at is None:
            story.first_published_at = now
        story.last_updated_at = now
        for link in story.articles:
            link.is_primary = link.article.id == primary.id
            link.similarity_score = 1 if link.is_primary else round(
                cosine(vectors[primary.id], vectors[link.article.id]), 6)
    db.flush()
    if review:
        review(groups, vectors, touched, decisions)
    if report:
        report({"eligible_unlinked_articles": len(pending), "assigned_articles": assigned,
                "excluded_articles": excluded, "stories": [{
                    "id": str(key), "created": key in created,
                    "primary_article_id": str(groups[key][0].id),
                    "article_ids": [str(a.id) for a in groups[key][1]],
                    "title": story_by_id[key].title, "context": story_by_id[key].context,
                    "img_url": story_by_id[key].img_url, "status": story_by_id[key].status.value,
                    "first_published_at": story_by_id[key].first_published_at.isoformat(),
                } for key in sorted(touched, key=str)]})
    return assigned
