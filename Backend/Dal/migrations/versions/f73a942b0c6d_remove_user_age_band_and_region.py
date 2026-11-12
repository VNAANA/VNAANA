"""Remove age band and region from user profiles."""

from alembic import op
import sqlalchemy as sa

revision = "f73a942b0c6d"
down_revision = "b71c9d06542a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "age_band")
    op.drop_column("users", "region")


def downgrade() -> None:
    op.add_column("users", sa.Column("age_band", sa.String(), nullable=True))
    op.add_column("users", sa.Column("region", sa.String(), nullable=True))
