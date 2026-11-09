"""Add an optional image URL to stories."""

from alembic import op
import sqlalchemy as sa

revision = "7b19a3fc820d"
down_revision = "af93290e72d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stories", sa.Column("img_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("stories", "img_url")
