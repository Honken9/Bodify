"""Tävlingsfas 2: egna ligor (klubbar) med medlemmar och ligautmaningar

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clubs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "creator_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("invite_code", sa.String(8), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_clubs_invite_code", "clubs", ["invite_code"], unique=True
    )
    op.create_table(
        "club_members",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "club_id",
            sa.Uuid(),
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
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
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("club_id", "user_id"),
    )
    with op.batch_alter_table("challenges") as batch:
        batch.add_column(sa.Column("club_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_challenges_club_id", "clubs", ["club_id"], ["id"], ondelete="SET NULL"
        )
    op.create_index("ix_challenges_club_id", "challenges", ["club_id"])


def downgrade() -> None:
    with op.batch_alter_table("challenges") as batch:
        batch.drop_index("ix_challenges_club_id")
        batch.drop_constraint("fk_challenges_club_id", type_="foreignkey")
        batch.drop_column("club_id")
    op.drop_table("club_members")
    op.drop_index("ix_clubs_invite_code", table_name="clubs")
    op.drop_table("clubs")
