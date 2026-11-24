"""Drop article_translations: descriptions are translated with the story.

Stories are now translated on request (the post's "Translate" button), and
the whole post, including the lead article's description, is saved in one
story_translations row (its description column). article_translations is no
longer used.

Revision ID: f2b8d4c07a15
Revises: c4e8f2a6d913
Create Date: 2026-11-24

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f2b8d4c07a15"
down_revision = "c4e8f2a6d913"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only cached text lives here; a story is translated again when the
    # user presses Translate.
    op.drop_table("article_translations")


def downgrade() -> None:
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
