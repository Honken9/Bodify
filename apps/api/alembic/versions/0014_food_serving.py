"""Livsmedel: gram per styck — logga "2 kex" istället för gram

Revision ID: 0014
Revises: 0013
Create Date: 2026-07-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "food_items", sa.Column("serving_g", sa.Numeric(7, 1), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("food_items", "serving_g")
