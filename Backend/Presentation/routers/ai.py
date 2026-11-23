"""AI endpoints for Articles and Stories."""

import uuid

from fastapi import APIRouter, HTTPException

from Backend.Logic.ai_service import AIInputError, AIModelError
from Backend.Logic.domain.story import StoryDetails, StoryStatus
from Backend.Logic.exceptions import NotFoundError
from Backend.Presentation.dependencies import AIServiceDep, StoryServiceDep
from Backend.Presentation.schemas.ai import AIResponse, AskRequest, StoryAskRequest, SummarizeRequest


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/stories/{story_id}/ask", response_model=AIResponse)
def ask_story(story_id: uuid.UUID, body: StoryAskRequest, service: AIServiceDep, stories: StoryServiceDep):
    story = stories.get_story(story_id)
    if story.status != StoryStatus.published:
        raise NotFoundError("Story", story_id)
    articles = [link.article for link in story.articles] if isinstance(story, StoryDetails) else []
    try:
        return service.ask_story(
            articles, body.question, body.language,
            history=[message.model_dump() for message in body.history],
        )
    except AIInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIModelError as exc:
        raise HTTPException(status_code=503, detail="AI model unavailable or invalid response") from exc


@router.post("/summarize", response_model=AIResponse)
def summarize(body: SummarizeRequest, service: AIServiceDep):
    try:
        return service.summarize(
            article_text=body.article_text,
            language=body.language,
            source_url=str(body.source_url) if body.source_url else None,
        )
    except AIInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIModelError as exc:
        raise HTTPException(status_code=503, detail="AI model unavailable or invalid response") from exc


@router.post("/ask", response_model=AIResponse)
def ask(body: AskRequest, service: AIServiceDep):
    try:
        return service.ask(
            article_text=body.article_text,
            question=body.question,
            language=body.language,
            source_url=str(body.source_url) if body.source_url else None,
        )
    except AIInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIModelError as exc:
        raise HTTPException(status_code=503, detail="AI model unavailable or invalid response") from exc
