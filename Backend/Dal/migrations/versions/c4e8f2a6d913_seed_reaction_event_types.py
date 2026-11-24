"""Seed the reaction event types.

Likes and dislikes are stored as engagement events, not in story_reactions:
`like`, `dislike`, and `reaction_removed` for undoing either. POST
/users/{user_id}/events only accepts types listed in event_weights.

The weights mirror Logic/Algorithm/scoring.py REACTION_WEIGHTS, which stays
the source of truth. Only a story's latest reaction event counts
(Logic/Algorithm/reactions.py), so reaction_removed is worth 0.

Revision ID: c4e8f2a6d913
Revises: d5f7a9c21e60
Create Date: 2026-11-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert

revision: str = "c4e8f2a6d913"
down_revision: Union[str, Sequence[str], None] = "d5f7a9c21e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REACTION_EVENT_WEIGHTS = {
    "like": 2,
    "dislike": -5,
    "reaction_removed": 0,
}


def upgrade() -> None:
    """Insert missing types; an existing row keeps its weight."""
    event_weights = sa.table(
        "event_weights",
        sa.column("event_type", sa.String()),
        sa.column("weight", sa.Numeric(6, 2)),
    )
    op.execute(
        insert(event_weights)
        .values(
            [
                {"event_type": name, "weight": weight}
                for name, weight in REACTION_EVENT_WEIGHTS.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["event_type"])
    )


def downgrade() -> None:
    """Keep the rows: stored events reference them."""
    pass
