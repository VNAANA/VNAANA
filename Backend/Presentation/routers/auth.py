from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel

from Backend.Presentation.auth import AuthenticatedSubject
from Backend.Dal.repositories.auth_credentials import has_password
from Backend.Presentation.dependencies import DbSession

router = APIRouter(prefix="/auth", tags=["Authentication"])

class AuthIdentityRead(BaseModel):
    auth_provider: str
    auth_subject: UUID

@router.get("/me", response_model=AuthIdentityRead)
async def get_my_identity(subject: AuthenticatedSubject,) -> AuthIdentityRead:
    return AuthIdentityRead(auth_provider="supabase", auth_subject=subject,)


class PasswordStatus(BaseModel):
    enabled: bool


@router.get("/me/password-status", response_model=PasswordStatus)
def get_password_status(subject: AuthenticatedSubject, db: DbSession, response: Response) -> PasswordStatus:
    response.headers["Cache-Control"] = "no-store"
    try:
        enabled = has_password(db, subject)
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Password status is unavailable.") from exc
    if enabled is None:
        raise HTTPException(401, "Sign-in required.")
    return PasswordStatus(enabled=enabled)

