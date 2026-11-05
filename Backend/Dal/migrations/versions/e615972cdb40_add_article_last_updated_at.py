"""Record the last article revision time supplied by the publisher."""

from alembic import op
import sqlalchemy as sa


revision = "e615972cdb40"
down_revision = "78ac4d901b3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "last_updated_at")
