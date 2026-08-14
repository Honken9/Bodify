"""Tävlingsfas 1: dueller, Elo-liga, insatser och prestationsmärken

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-13

"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Insats ("förloraren bjuder på lunch") + betygsatt-flagga så
    # Elo-jobbet aldrig räknar samma utmaning två gånger
    op.add_column("challenges", sa.Column("stake", sa.String(200), nullable=True))
    op.add_column(
        "challenges",
        sa.Column("rated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Shapiqo-ligan: Elo-rating per användare
    op.add_column(
        "users",
        sa.Column("elo_rating", sa.Integer(), nullable=False, server_default="1000"),
    )
    # Prestationsmärken
    op.create_table(
        "badges",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(40), primary_key=True),
        sa.Column(
            "earned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("badges")
    op.drop_column("users", "elo_rating")
    with op.batch_alter_table("challenges") as batch:
        batch.drop_column("rated")
        batch.drop_column("stake")
