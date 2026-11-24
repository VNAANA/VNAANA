"""Add optional description text to story translations."""

import sqlalchemy as sa
from alembic import op

revision = "d5f7a9c21e60"
down_revision = "c4e8f2a61d97"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "story_translations", sa.Column("description", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("story_translations", "description")
