"""Livsmedel: enhet g/ml — drycker loggas i milliliter

Revision ID: 0018
Revises: 0017
Create Date: 2026-07-19

"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None

# Basposter som mäts i ml (densitet ≈ 1 → värdet lagras oförändrat)
DRINK_PATTERNS = [
    "Coca-Cola%",
    "Fanta%",
    "Sprite%",
    "Pepsi%",
    "Loka%",
    "Milkshake%",
    "Caffè Latte%",
    "Cappuccino%",
    "Iskaffe%",
    "Chai Latte%",
]


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column("unit", sa.String(2), nullable=False, server_default="g"),
    )
    for pattern in DRINK_PATTERNS:
        op.execute(
            "UPDATE food_items SET unit = 'ml' "
            f"WHERE source = 'base' AND name LIKE '{pattern}'"
        )


def downgrade() -> None:
    op.drop_column("food_items", "unit")
