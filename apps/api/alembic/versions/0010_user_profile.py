"""Användarprofil: foto, ort och favoritträningsfrågor

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_path", sa.String(300), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("users", "profile")
    op.drop_column("users", "avatar_path")
