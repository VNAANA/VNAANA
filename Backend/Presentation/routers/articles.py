"""Articles endpoints."""

import uuid

from fastapi import APIRouter, Query, Response, status

from Backend.Presentation.dependencies import (
    ArticleServiceDep,
)
from Backend.Presentation.schemas.articles import (
    ArticleCreate,
    ArticleRead,
)


router = APIRouter(
    prefix="/articles",
    tags=["articles"],
)


@router.get(
    "",
    response_model=list[ArticleRead],
)
def list_articles(
    service: ArticleServiceDep,
    provider_id: uuid.UUID | None = None,
    language: str | None = Query(
        None,
        max_length=5,
    ),
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
):
    return service.list_articles(
        provider_id=provider_id,
        language=language,
        limit=limit,
        offset=offset,
    )


# Must stay above GET /{article_id}: FastAPI matches routes in order, and
# "random" would otherwise be parsed as an article id (422).
@router.get(
    "/random",
    response_model=list[ArticleRead],
)
def list_random_articles(
    service: ArticleServiceDep,
    limit: int = Query(
        5,
        ge=1,
        le=20,
    ),
):
    return service.list_random_articles(
        limit=limit,
    )


@router.post(
    "",
    response_model=ArticleRead,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": (
                "Article already existed; "
                "last_seen_at was refreshed"
            )
        }
    },
)
def ingest_article(
    body: ArticleCreate,
    response: Response,
    service: ArticleServiceDep,
):
    article, created = service.ingest_article(
        body.model_dump(),
    )

    if not created:
        response.status_code = status.HTTP_200_OK

    return article


@router.get(
    "/{article_id}",
    response_model=ArticleRead,
)
def get_article(
    article_id: uuid.UUID,
    service: ArticleServiceDep,
):
    return service.get_article(article_id)