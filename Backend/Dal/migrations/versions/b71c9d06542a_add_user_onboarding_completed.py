"""Track whether the user completed personalization."""

import sqlalchemy as sa
from alembic import op

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
