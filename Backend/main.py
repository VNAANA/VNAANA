"""VNAANA API entry point.

Run:   (from the VNAANA folder) uvicorn Backend.main:app --reload
Docs:  http://localhost:8000/docs

Layers:
  presentation/  HTTP: routers, request/response schemas, error mapping
  logic/         business rules (services), no HTTP and no SQL
  dal/           database: models, session, repositories
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Backend.Presentation.error_handlers import register_error_handlers
from Backend.Presentation.rate_limit import add_rate_limiting
from Backend.Presentation.routers import ai, articles, auth, login, stories, tags, users

app = FastAPI(
    title="VNAANA API",
    description="Backend for the Virtual News Anchor Against News Avoidance project.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Authentication"},
        {"name": "users"},
        {"name": "stories"},
        {"name": "articles"},
        {"name": "ai"},
        {"name": "tags"},
    ],
)

# Added before CORS on purpose: the last middleware added runs first, so CORS
# answers preflight requests before the limiter counts them, and still adds
# its headers to a 429 so the frontend can read it.
add_rate_limiting(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

register_error_handlers(app)

app.include_router(login.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(stories.router)
app.include_router(articles.router)
app.include_router(ai.router)
app.include_router(tags.router)
