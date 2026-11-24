"""Seed the event types the frontend sends.

POST /users/{user_id}/events only accepts event types listed in
event_weights (404 otherwise), and the table was empty, so no event could be
stored. These are the two types the For You scoring counts
(Logic/Algorithm/scoring.py EVENT_WEIGHTS). That dict stays the source of
truth for the weights; the column here only mirrors it.

Revision ID: a3d5e7f91b20
Revises: b83c1e5a902d
Create Date: 2026-11-24

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert


revision: str = "a3d5e7f91b20"
down_revision: Union[str, Sequence[str], None] = "b83c1e5a902d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EVENT_WEIGHTS = {
    "share": 5,
    "read_complete": 1,
}


def upgrade() -> None:
    """Insert missing types; an existing row keeps its weight."""
    event_weights = sa.table(
        "event_weights",
        sa.column("event_type", sa.String()),
        sa.column("weight", sa.Numeric(6, 2)),
    )
    rows = [{"event_type": name, "weight": weight} for name, weight in EVENT_WEIGHTS.items()]
    op.execute(insert(event_weights).values(rows).on_conflict_do_nothing(index_elements=["event_type"]))


def downgrade() -> None:
    """Keep the rows: stored events reference them."""
    pass
