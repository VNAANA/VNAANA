"""Add provider sources.

Revision ID: 78ac4d901b3e
Revises: c91e4a72b608
"""

from alembic import op
import sqlalchemy as sa


revision = "78ac4d901b3e"
down_revision = "c91e4a72b608"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_sources",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("provider_id", sa.UUID(), sa.ForeignKey("providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("poll_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
    )
    op.create_index("ix_provider_sources_provider_id", "provider_sources", ["provider_id"])
    op.create_index("ix_provider_sources_is_active", "provider_sources", ["is_active"])


def downgrade() -> None:
    op.drop_table("provider_sources")
