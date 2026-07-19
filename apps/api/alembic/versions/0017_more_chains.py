"""Fler kedjor i matkatalogen: Espresso House, Subway och Taco Bar.

Typvärden per 100 g från kedjornas näringsinformation (avrundade),
serving_g = normalportion.

Revision ID: 0017
Revises: 0016
Create Date: 2026-07-19

"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def _p(kcal, protein, carbs, fat):
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}


CATALOG = [
    # ── Espresso House ────────────────────────────────────────
    ("Caffè Latte mellan", "Espresso House", _p(45, 2.4, 3.6, 2.4), 400),
    ("Cappuccino", "Espresso House", _p(40, 2.2, 3.3, 2.1), 300),
    ("Iskaffe", "Espresso House", _p(70, 2.5, 9, 2.5), 400),
    ("Chai Latte", "Espresso House", _p(75, 1.8, 13, 1.8), 400),
    ("Kanelbulle", "Espresso House", _p(370, 6, 47, 17), 120),
    ("Kardemummabulle", "Espresso House", _p(380, 6, 45, 19), 120),
    ("Croissant", "Espresso House", _p(410, 8, 40, 24), 75),
    ("Chokladboll", "Espresso House", _p(430, 5, 45, 25), 75),
    ("Morotskaka", "Espresso House", _p(390, 4, 43, 22), 130),
    ("Sandwich mozzarella pesto", "Espresso House", _p(250, 9, 26, 12), 190),
    # ── Subway ────────────────────────────────────────────────
    ("Sub 15 cm Kyckling", "Subway", _p(150, 10, 20, 3), 230),
    ("Sub 15 cm Turkey", "Subway", _p(140, 9, 20, 2.5), 220),
    ("Sub 15 cm Italian BMT", "Subway", _p(200, 10, 19, 9), 230),
    ("Sub 15 cm Tuna", "Subway", _p(210, 9, 18, 11), 240),
    ("Sub 15 cm Meatball Marinara", "Subway", _p(180, 8, 20, 7), 290),
    ("Sub 15 cm Veggie Delite", "Subway", _p(120, 4, 22, 1.5), 170),
    ("Sub 30 cm Kyckling", "Subway", _p(150, 10, 20, 3), 460),
    ("Cookie chocolate chip", "Subway", _p(480, 5, 62, 23), 45),
    ("Nachos", "Subway", _p(480, 7, 55, 25), 45),
    # ── Taco Bar ──────────────────────────────────────────────
    ("Taco soft nötkött", "Taco Bar", _p(190, 9, 18, 9), 140),
    ("Taco crispy nötkött", "Taco Bar", _p(220, 10, 18, 12), 105),
    ("Burrito nötkött", "Taco Bar", _p(180, 9, 20, 7), 330),
    ("Burrito kyckling", "Taco Bar", _p(170, 10, 20, 6), 330),
    ("Quesadilla kyckling", "Taco Bar", _p(230, 12, 20, 11), 280),
    ("Tacosallad", "Taco Bar", _p(130, 7, 8, 8), 380),
    ("Nachotallrik", "Taco Bar", _p(210, 8, 20, 11), 400),
    ("Churros", "Taco Bar", _p(390, 4, 46, 21), 100),
]

CHAINS = sorted({brand for _, brand, _, _ in CATALOG})


def upgrade() -> None:
    food_items = sa.table(
        "food_items",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("brand", sa.String()),
        sa.column("source", sa.String()),
        sa.column("per_100g", sa.JSON()),
        sa.column("serving_g", sa.Numeric()),
    )
    op.bulk_insert(
        food_items,
        [
            {
                "id": uuid.uuid4(),
                "name": name,
                "brand": brand,
                "source": "base",
                "per_100g": per_100g,
                "serving_g": serving_g,
            }
            for name, brand, per_100g, serving_g in CATALOG
        ],
    )


def downgrade() -> None:
    chains = ", ".join(f"'{c}'" for c in CHAINS)
    op.execute(
        f"DELETE FROM food_items WHERE source = 'base' AND brand IN ({chains})"
    )
