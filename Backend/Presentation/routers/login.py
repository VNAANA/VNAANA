"""Exchange email/password with Supabase; never provision a VNA profile here."""

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import ValidationError

from Backend.config import get_settings
from Backend.Presentation.schemas.auth import AccessTokenRead, PasswordLogin


class LoginRoute(APIRoute):
    """Do not echo credential inputs in validation errors; never cache login responses."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def secured_handler(request: Request) -> Response:
            try:
                response = await handler(request)
            except RequestValidationError:
                response = JSONResponse(status_code=422, content={
                    "detail": "Provide a valid email and a non-empty password."
                })
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code,
                                        content={"detail": exc.detail}, headers=exc.headers)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            return response

        return secured_handler


router = APIRouter(prefix="/auth", tags=["Authentication"], route_class=LoginRoute)


@router.post("/login", response_model=AccessTokenRead, responses={
    401: {"description": "Sign-in failed"},
    429: {"description": "Too many sign-in attempts"},
    502: {"description": "Unexpected authentication response"},
    503: {"description": "Authentication unavailable"},
})
async def login(body: PasswordLogin) -> AccessTokenRead:
    """Sign in with a configured password. Copy access_token into Swagger Authorize.

    This does not register users, create VNA profiles, or return refresh tokens.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(503, "Authentication is not configured.")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            result = await client.post(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/token",
                params={"grant_type": "password"},
                headers={"apikey": settings.supabase_publishable_key},
                json={"email": body.email, "password": body.password.get_secret_value()},
            )
    except httpx.RequestError:
        raise HTTPException(503, "Authentication service is unavailable.") from None

    if result.status_code == 429:
        raise HTTPException(429, "Too many sign-in attempts. Please try again later.")
    if result.status_code in (400, 401, 403, 422):
        raise HTTPException(401, "Sign-in failed. Check your credentials and email confirmation.")
    if result.status_code != 200:
        raise HTTPException(503, "Authentication service could not complete sign-in.")
    try:
        # Ignore user metadata and refresh_token; expose only the documented fields.
        return AccessTokenRead.model_validate(result.json())
    except (ValueError, ValidationError):
        raise HTTPException(502, "Authentication service returned an unexpected response.") from None
