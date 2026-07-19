"""Utmaningar v2: öppna utmaningar, vane-läge och heja-flöde

Revision ID: 0015
Revises: 0014
Create Date: 2026-07-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "challenges",
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "challenges",
        sa.Column("kind", sa.String(20), nullable=False, server_default="standard"),
    )
    op.add_column("challenges", sa.Column("target", sa.JSON(), nullable=True))

    op.create_table(
        "challenge_cheers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "challenge_id",
            sa.Uuid(),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("item_kind", sa.String(10), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column(
            "actor_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("challenge_id", "item_kind", "item_id", "actor_id"),
    )


def downgrade() -> None:
    op.drop_table("challenge_cheers")
    op.drop_column("challenges", "target")
    op.drop_column("challenges", "kind")
    op.drop_column("challenges", "is_open")
