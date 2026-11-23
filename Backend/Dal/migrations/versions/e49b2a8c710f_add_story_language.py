"""Add an optional language code to stories."""

import sqlalchemy as sa
from alembic import op

revision = "e49b2a8c710f"
down_revision = "d82e6a193b47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("language", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "language")
