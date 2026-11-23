"""Replace story language with optional English translation fields.

Dropping columns discards their values; downgrade restores schema, not data.
"""

import sqlalchemy as sa
from alembic import op

revision = "a62f9c10d843"
down_revision = "e49b2a8c710f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("eng_title", sa.Text(), nullable=True))
    op.add_column("stories", sa.Column("eng_summary", sa.Text(), nullable=True))
    op.add_column("stories", sa.Column("eng_context", sa.Text(), nullable=True))
    op.drop_column("stories", "language")


def downgrade() -> None:
    op.add_column("stories", sa.Column("language", sa.String(), nullable=True))
    op.drop_column("stories", "eng_context")
    op.drop_column("stories", "eng_summary")
    op.drop_column("stories", "eng_title")
