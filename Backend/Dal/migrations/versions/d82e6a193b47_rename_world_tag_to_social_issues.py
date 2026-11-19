"""Rename the World tag to Social Issues, preserving its ID and relationships."""

from alembic import op
import sqlalchemy as sa

revision = "d82e6a193b47"
down_revision = "f73a942b0c6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The unique name constraint rejects a collision rather than merging tags.
    tags = sa.table("tags", sa.column("name", sa.String()))
    op.execute(tags.update().where(tags.c.name == "World").values(name="Social Issues"))


def downgrade() -> None:
    tags = sa.table("tags", sa.column("name", sa.String()))
    op.execute(tags.update().where(tags.c.name == "Social Issues").values(name="World"))
