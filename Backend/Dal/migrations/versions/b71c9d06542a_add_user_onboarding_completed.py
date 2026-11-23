"""Track whether the user completed personalization."""

from alembic import op
import sqlalchemy as sa


revision = "b71c9d06542a"
down_revision = "7b19a3fc820d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
