"""Cache translated article descriptions per article and language."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4e8f2a61d97"
down_revision = "a3d5e7f91b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "article_translations",
        sa.Column("article_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("source_description", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("article_id", "language"),
    )


def downgrade() -> None:
    # Only cached translations live here; they are made again on the next request.
    op.drop_table("article_translations")
