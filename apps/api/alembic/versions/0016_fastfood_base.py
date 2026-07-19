"""Inbyggd snabbmatskatalog: svenska kedjor (McDonald's, Max, Sibylla,
ChopChop, Burger King, gatukök) + vanliga drycker.

Näringsvärden per 100 g är typvärden från kedjornas näringsdeklarationer
(avrundade) och serving_g är normalportionen — så "1 st Big Mac" funkar.

Revision ID: 0016
Revises: 0015
Create Date: 2026-07-19

"""
import uuid

from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def _p(kcal, protein, carbs, fat):
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat}


# (namn, kedja, per_100g, portionsvikt g)
CATALOG = [
    # ── McDonald's ────────────────────────────────────────────
    ("Big Mac", "McDonald's", _p(230, 12, 18, 12), 220),
    ("Cheeseburgare", "McDonald's", _p(250, 13, 27, 10), 115),
    ("Hamburgare", "McDonald's", _p(240, 12, 29, 8), 100),
    ("Dubbel cheeseburgare", "McDonald's", _p(250, 15, 20, 13), 170),
    ("Quarter Pounder Cheese", "McDonald's", _p(240, 14, 15, 13), 200),
    ("Big Tasty", "McDonald's", _p(250, 12, 15, 16), 340),
    ("McFeast", "McDonald's", _p(230, 12, 16, 13), 280),
    ("McChicken", "McDonald's", _p(220, 11, 18, 11), 190),
    ("Chicken McNuggets 6 st", "McDonald's", _p(270, 15, 15, 17), 100),
    ("Chicken McNuggets 9 st", "McDonald's", _p(270, 15, 15, 17), 150),
    ("Pommes frites liten", "McDonald's", _p(310, 3.5, 41, 14), 80),
    ("Pommes frites mellan", "McDonald's", _p(310, 3.5, 41, 14), 115),
    ("Pommes frites stor", "McDonald's", _p(310, 3.5, 41, 14), 150),
    ("McFlurry Oreo", "McDonald's", _p(180, 4, 27, 6), 190),
    ("Sundae karamell", "McDonald's", _p(170, 4, 30, 4), 150),
    ("Äppelpaj", "McDonald's", _p(240, 2.5, 32, 11), 80),
    # ── Max ───────────────────────────────────────────────────
    ("Originalburgare", "Max", _p(220, 13, 20, 10), 160),
    ("Grand Deluxe Original", "Max", _p(240, 13, 14, 15), 250),
    ("Frisco Original", "Max", _p(250, 12, 15, 16), 260),
    ("Halloumiburgare", "Max", _p(250, 11, 20, 14), 230),
    ("Grön burgare", "Max", _p(210, 8, 22, 10), 230),
    ("Maxade pommes mellan", "Max", _p(300, 3.5, 40, 14), 120),
    ("Maxade pommes stor", "Max", _p(300, 3.5, 40, 14), 160),
    ("Chilicheese 5 st", "Max", _p(280, 8, 25, 16), 110),
    ("Milkshake choklad", "Max", _p(120, 3, 18, 4), 400),
    # ── Burger King ───────────────────────────────────────────
    ("Whopper", "Burger King", _p(230, 11, 18, 13), 270),
    ("Cheeseburgare", "Burger King", _p(250, 13, 26, 11), 120),
    ("Chicken Royale", "Burger King", _p(240, 11, 20, 13), 220),
    ("King Pommes mellan", "Burger King", _p(300, 3.5, 40, 14), 116),
    ("Onion Rings", "Burger King", _p(290, 4, 38, 13), 90),
    # ── Sibylla ───────────────────────────────────────────────
    ("Grillkorv med bröd", "Sibylla", _p(270, 10, 24, 15), 150),
    ("Kokt korv med bröd", "Sibylla", _p(230, 9, 24, 11), 150),
    ("Hamburgare original", "Sibylla", _p(240, 12, 22, 12), 180),
    ("Tunnbrödsrulle korv & mos", "Sibylla", _p(180, 6, 22, 8), 350),
    ("Pommes frites", "Sibylla", _p(300, 3.5, 40, 14), 120),
    # ── ChopChop ──────────────────────────────────────────────
    ("Chicken Teriyaki med ris", "ChopChop", _p(135, 8, 19, 3), 450),
    ("Beef Teriyaki med ris", "ChopChop", _p(140, 9, 18, 4), 450),
    ("Sweet & Sour Chicken med ris", "ChopChop", _p(150, 7, 22, 4), 450),
    ("Chicken Noodles", "ChopChop", _p(150, 8, 19, 5), 400),
    ("Vårrullar 2 st", "ChopChop", _p(220, 6, 25, 10), 120),
    # ── Gatukök & pizzeria ────────────────────────────────────
    ("Kebabtallrik", "Gatukök", _p(160, 10, 12, 8), 550),
    ("Kebabrulle", "Gatukök", _p(180, 10, 18, 8), 450),
    ("Kebab med bröd", "Gatukök", _p(200, 12, 18, 9), 350),
    ("Falafelrulle", "Gatukök", _p(170, 6, 22, 7), 400),
    ("Pizza Vesuvio", "Pizzeria", _p(230, 11, 28, 8), 400),
    ("Pizza Margherita", "Pizzeria", _p(225, 10, 28, 8), 380),
    ("Pizza Kebabpizza", "Pizzeria", _p(200, 11, 22, 8), 450),
    ("Pizza Hawaii", "Pizzeria", _p(215, 10, 27, 7), 420),
    # ── Drycker ───────────────────────────────────────────────
    ("Coca-Cola 33 cl", "Coca-Cola", _p(42, 0, 10.6, 0), 330),
    ("Coca-Cola Zero 33 cl", "Coca-Cola", _p(0.3, 0, 0, 0), 330),
    ("Fanta 33 cl", "Fanta", _p(39, 0, 9.5, 0), 330),
    ("Sprite 33 cl", "Sprite", _p(37, 0, 9, 0), 330),
    ("Pepsi Max 33 cl", "Pepsi", _p(0.4, 0, 0, 0), 330),
    ("Loka citron 33 cl", "Loka", _p(0, 0, 0, 0), 330),
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
