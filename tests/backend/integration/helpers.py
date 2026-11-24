"""Small helpers shared by the integration tests."""

from datetime import datetime


def naive(moment: datetime | None) -> datetime | None:
    """SQLite drops tzinfo, so compare timestamps without it (all times here are UTC)."""
    return None if moment is None else moment.replace(tzinfo=None)
