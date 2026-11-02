"""Seed the twelve default news tags.

Revision ID: c91e4a72b608
Revises: fdf3a95033c6
Create Date: 2026-11-02

"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert


revision: str = "c91e4a72b608"
down_revision: Union[str, Sequence[str], None] = "fdf3a95033c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TAG_NAMES = (
    "Politics",
    "Technology",
    "Sports",
    "Climate",
    "Economy",
    "Health",
    "Entertainment",
    "World",
    "Culture",
    "Science",
    "Domestic",
    "International",
)


def upgrade() -> None:
    """Insert missing names; a duplicate name preserves the existing row."""
    tags = sa.table(
        "tags",
        sa.column("id", sa.UUID()),
        sa.column("name", sa.String()),
    )
    # Supply IDs explicitly: the model's Python default is not a server default.
    rows = [
        {"id": uuid.uuid5(uuid.NAMESPACE_URL, f"vnaana:default-tag:{name}"), "name": name}
        for name in TAG_NAMES
    ]
    op.execute(insert(tags).values(rows).on_conflict_do_nothing(index_elements=["name"]))


def downgrade() -> None:
    """Retain tags and their relationships when rolling back the revision."""
    pass
