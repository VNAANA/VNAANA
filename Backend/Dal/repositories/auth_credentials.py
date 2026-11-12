from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def has_password(db: Session, subject: UUID) -> bool | None:
    """Return only whether the verified account has a password credential."""
    return db.scalar(text("""
        SELECT COALESCE(encrypted_password <> '', false)
        FROM auth.users WHERE id = :subject
    """), {"subject": subject})
