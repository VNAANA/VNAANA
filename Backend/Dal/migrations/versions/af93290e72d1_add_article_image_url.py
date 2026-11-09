"""Add an optional image URL to articles."""

from alembic import op
import sqlalchemy as sa

revision = "af93290e72d1"
down_revision = "e615972cdb40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("img_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "img_url")
