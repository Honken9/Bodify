"""Socialt: vänner, utmaningar, deltagare, snapshots

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "friend_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "friend_id"),
    )

    op.create_table(
        "challenges",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "creator_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("metric", sa.String(30), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "challenge_participants",
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
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.UniqueConstraint("challenge_id", "user_id"),
    )

    op.create_table(
        "challenge_snapshots",
        sa.Column(
            "challenge_id",
            sa.Uuid(),
            sa.ForeignKey("challenges.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("value", sa.Numeric(12, 3), nullable=False),
    )

    # Obs: sociala tabeller är medvetet delade mellan deltagare — RLS
    # appliceras inte här; åtkomst styrs i applikationslagret
    # (vänskaps- och deltagarkontroller).


def downgrade() -> None:
    for table in (
        "challenge_snapshots",
        "challenge_participants",
        "challenges",
        "friendships",
    ):
        op.drop_table(table)
