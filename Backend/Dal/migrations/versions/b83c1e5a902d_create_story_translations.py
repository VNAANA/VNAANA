"""Move English story text into a language-specific translations table."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b83c1e5a902d"
down_revision = "a62f9c10d843"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_translations",
        sa.Column("story_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["story_id"], ["stories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("story_id", "language"),
    )
    # Preserve partial translations too; do not manufacture rows for untranslated stories.
    op.execute(sa.text("""
        INSERT INTO story_translations (story_id, language, title, summary, context)
        SELECT id, 'en', eng_title, eng_summary, eng_context FROM stories
        WHERE eng_title IS NOT NULL OR eng_summary IS NOT NULL OR eng_context IS NOT NULL
    """))
    for name in ("eng_context", "eng_summary", "eng_title"):
        op.drop_column("stories", name)


def downgrade() -> None:
    # The old schema cannot represent other languages; refuse to silently discard them.
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM story_translations WHERE language <> 'en' LIMIT 1"
    )).first() is not None:
        raise RuntimeError("Cannot downgrade while non-English translations exist; export and resolve them first.")
    for name in ("eng_title", "eng_summary", "eng_context"):
        op.add_column("stories", sa.Column(name, sa.Text(), nullable=True))
    op.execute(sa.text("""
        UPDATE stories SET
            eng_title = (SELECT title FROM story_translations WHERE story_id = stories.id AND language = 'en'),
            eng_summary = (SELECT summary FROM story_translations WHERE story_id = stories.id AND language = 'en'),
            eng_context = (SELECT context FROM story_translations WHERE story_id = stories.id AND language = 'en')
    """))
    op.drop_table("story_translations")
