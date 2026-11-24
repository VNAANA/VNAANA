"""/stories endpoints. Plain `def` on purpose, see routers/users.py."""

import uuid

from fastapi import APIRouter, Query, status

from Backend.Logic.domain.story import StoryStatus
from Backend.Presentation.auth import AuthenticatedSubject, OptionalSubject
from Backend.Presentation.dependencies import (
    AlgorithmServiceDep,
    StoryServiceDep,
    UserServiceDep,
)
from Backend.Presentation.schemas.feed import FeedRead
from Backend.Presentation.schemas.stories import (
    StoryArticleLink,
    StoryArticleRead,
    StoryArticlesPageRead,
    StoryCardRead,
    StoryCreate,
    StoryRead,
    StoryTagsUpdate,
    StoryUpdate,
)

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("/{story_id}/articles", response_model=StoryArticlesPageRead)
def get_story_articles(
    story_id: uuid.UUID,
    service: StoryServiceDep,
    limit: int = Query(20, ge=0, le=100),
    offset: int = Query(0, ge=0),
):
    return service.list_articles(story_id, limit=limit, offset=offset)


@router.get("", response_model=list[StoryCardRead])
def list_stories(
    service: StoryServiceDep,
    status_filter: StoryStatus | None = Query(
        StoryStatus.published,
        alias="status",
    ),
    tag_id: list[uuid.UUID] | None = Query(
        None,
        max_length=50,
        description="Repeat to filter by several tags: stories with any of them.",
    ),
    q: str | None = Query(
        None,
        max_length=100,
        description="Words that must all appear in the title. With tag_id, only those tags' stories are searched.",
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return service.list_stories(
        status=status_filter,
        tag_ids=tag_id,
        q=q,
        limit=limit,
        offset=offset,
    )


# Must stay above GET /{story_id}: FastAPI matches routes in order, and
# "for-you" would otherwise be parsed as a story id (422).
@router.get("/for-you", response_model=FeedRead)
def get_for_you(
    service: AlgorithmServiceDep,
    stories: StoryServiceDep,
    subject: AuthenticatedSubject,
    users: UserServiceDep,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user = users.get_authenticated_user(subject)
    return stories.with_cards(
        service.get_feed(
            user.id,
            limit=limit,
            offset=offset,
        )
    )


@router.post(
    "",
    response_model=StoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_story(
    body: StoryCreate,
    service: StoryServiceDep,
):
    return service.create_story(
        body.model_dump(),
    )


@router.get(
    "/{story_id}",
    response_model=StoryRead,
    responses={
        503: {
            "description": "The story needed translating and the translation service failed"
        },
    },
)
def get_story(
    story_id: uuid.UUID,
    service: StoryServiceDep,
    users: UserServiceDep,
    subject: OptionalSubject,
):
    """Signed in: the story in the user's profile language, translated on
    first request and cached after that. Signed out: the original story."""
    language = users.get_preferred_language(subject)
    return service.get_story_in_language(story_id, language)


@router.patch("/{story_id}", response_model=StoryRead)
def update_story(
    story_id: uuid.UUID,
    body: StoryUpdate,
    service: StoryServiceDep,
):
    return service.update_story(
        story_id,
        body.model_dump(exclude_unset=True),
    )


@router.put("/{story_id}/tags", response_model=StoryRead)
def set_story_tags(
    story_id: uuid.UUID,
    body: StoryTagsUpdate,
    service: StoryServiceDep,
):
    tag_data = {tag.tag_id: tag.relevance_score for tag in body.tags}

    return service.set_tags(
        story_id,
        tag_data,
    )


@router.post(
    "/{story_id}/articles",
    response_model=StoryArticleRead,
    status_code=status.HTTP_201_CREATED,
)
def link_article(
    story_id: uuid.UUID,
    body: StoryArticleLink,
    service: StoryServiceDep,
):
    return service.link_article(
        story_id,
        body.article_id,
        body.similarity_score,
        body.is_primary,
    )


@router.delete(
    "/{story_id}/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_article(
    story_id: uuid.UUID,
    article_id: uuid.UUID,
    service: StoryServiceDep,
):
    service.unlink_article(
        story_id,
        article_id,
    )
