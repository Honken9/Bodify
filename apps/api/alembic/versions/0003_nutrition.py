"""Kost: livsmedel, måltidsposter, mallar, näringsmål

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column("name", sa.String(200), nullable=False, index=True),
        sa.Column("brand", sa.String(120), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="custom"),
        sa.Column("per_100g", sa.JSON(), nullable=False),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_food_items_barcode", "food_items", ["barcode"], unique=True)

    op.create_table(
        "meal_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("eaten_on", sa.Date(), nullable=False, index=True),
        sa.Column("meal", sa.String(20), nullable=False),
        sa.Column(
            "food_item_id",
            sa.Uuid(),
            sa.ForeignKey("food_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grams", sa.Numeric(7, 1), nullable=False),
        sa.Column("kcal", sa.Numeric(8, 1), nullable=False, server_default="0"),
        sa.Column("protein_g", sa.Numeric(7, 1), nullable=False, server_default="0"),
        sa.Column("carbs_g", sa.Numeric(7, 1), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Numeric(7, 1), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "meal_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("items", sa.JSON(), nullable=False),
    )

    op.create_table(
        "nutrition_targets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kcal", sa.Integer(), nullable=False, server_default="2500"),
        sa.Column("protein_g", sa.Integer(), nullable=False, server_default="150"),
        sa.Column("carbs_g", sa.Integer(), nullable=False, server_default="250"),
        sa.Column("fat_g", sa.Integer(), nullable=False, server_default="80"),
    )
    op.create_index(
        "ix_nutrition_targets_user_id", "nutrition_targets", ["user_id"], unique=True
    )

    if op.get_bind().dialect.name == "postgresql":
        uid = "current_setting('app.user_id', true)::uuid"
        op.execute("ALTER TABLE food_items ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant ON food_items USING (source = 'off' OR created_by = {uid})"
        )
        for table in ("meal_entries", "meal_templates", "nutrition_targets"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant ON {table} USING (user_id = {uid})")


def downgrade() -> None:
    for table in ("nutrition_targets", "meal_templates", "meal_entries", "food_items"):
        op.drop_table(table)
