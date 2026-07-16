"""Inbjudningar till utmaningar

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-16

"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "challenge_invites",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.Uuid(),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "invited_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("challenge_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("challenge_invites")
