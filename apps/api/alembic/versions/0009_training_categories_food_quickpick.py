"""Träningskategorier (enstaka pass) + favoriter och basförslag i kosten

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-17

"""
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Färdiga enstaka pass (kind="single") — startas direkt utan att aktivera
# något program. (namn, beskrivning, nivå, [(övning, set, reps, vila)])
SINGLE_WORKOUTS = [
    (
        "HIIT Express 20 min",
        "Kort och svettigt — fyra övningar, högt tempo, ingen utrustning "
        "utom en kettlebell.",
        "beginner",
        [
            ("Burpees", 4, "12", 45),
            ("Kettlebell swings", 4, "15", 45),
            ("Armhävningar", 4, "10-15", 45),
            ("Sit-ups", 4, "15", 45),
        ],
    ),
    (
        "Core 15 min",
        "Snabb mage/bål-rutin som funkar var som helst.",
        "beginner",
        [
            ("Plankan", 3, "30-60 s", 45),
            ("Sidoplanka", 3, "30 s/sida", 45),
            ("Russian twists", 3, "20", 30),
            ("Hängande benlyft", 3, "10-12", 60),
        ],
    ),
    (
        "Helkropp express 30 min",
        "Tre baslyft när tiden är knapp — hela kroppen på en halvtimme.",
        "intermediate",
        [
            ("Knäböj", 3, "8-10", 120),
            ("Bänkpress", 3, "8-10", 120),
            ("Skivstångsrodd", 3, "8-10", 120),
        ],
    ),
    (
        "Överkropp pump 40 min",
        "Bröst, rygg, axlar och armar — perfekt fristående gympass.",
        "intermediate",
        [
            ("Hantelpress", 3, "10-12", 90),
            ("Latsdrag", 3, "10-12", 90),
            ("Sidolyft", 3, "12-15", 60),
            ("Hantelcurl", 3, "10-12", 60),
            ("Pushdowns", 3, "10-12", 60),
        ],
    ),
    (
        "Ben & rumpa 30 min",
        "Underkroppsfokus med hantlar eller kroppsvikt.",
        "beginner",
        [
            ("Goblet squat", 3, "10-12", 90),
            ("Utfall", 3, "10/ben", 90),
            ("Höftlyft", 3, "12-15", 60),
            ("Stående vadpress", 3, "15", 45),
        ],
    ),
]

# Basförslag i livsmedelsbiblioteket (source="base") — typvärden per 100 g
# i stil med Livsmedelsverkets tabeller. Synliga för alla användare.
# (namn, kcal, protein, kolhydrater, fett, fiber|None)
BASE_FOODS = [
    ("Kokt ägg", 155, 13, 1.1, 11, None),
    ("Havregryn", 370, 13, 58, 7, 10),
    ("Mellanmjölk", 47, 3.5, 4.9, 1.5, None),
    ("Kycklingfilé, tillagad", 150, 29, 0, 3.3, None),
    ("Nötfärs 10 %, stekt", 190, 26, 0, 10, None),
    ("Lax, ugnsbakad", 200, 22, 0, 12, None),
    ("Tonfisk i vatten", 105, 24, 0, 0.8, None),
    ("Jasminris, kokt", 130, 2.7, 28, 0.3, None),
    ("Pasta, kokt", 130, 5, 25, 1.1, 1.8),
    ("Potatis, kokt", 80, 1.7, 18, 0.1, 1.7),
    ("Fullkornsbröd", 250, 9, 42, 3.5, 6.5),
    ("Knäckebröd, råg", 350, 9, 60, 1.5, 17),
    ("Kvarg, naturell", 63, 11, 3.8, 0.3, None),
    ("Grekisk yoghurt 10 %", 120, 4.5, 3.5, 10, None),
    ("Vassleprotein, pulver", 380, 75, 8, 6, None),
    ("Banan", 93, 1.1, 21, 0.3, 1.9),
    ("Äpple", 54, 0.3, 12, 0.2, 2.2),
    ("Broccoli, kokt", 30, 2.8, 3, 0.4, 2.7),
    ("Tomat", 20, 0.9, 3.4, 0.2, 1.2),
    ("Olivolja", 884, 0, 0, 100, None),
    ("Smör", 730, 0.5, 0.7, 81, None),
]


def upgrade() -> None:
    # 1) Programtyp: "program" (flerdagars rotation) eller "single"
    #    (fristående pass som startas direkt).
    op.add_column(
        "programs",
        sa.Column(
            "kind", sa.String(20), nullable=False, server_default="program"
        ),
    )

    # 2) Favoritmarkerade livsmedel per användare
    op.create_table(
        "food_favorites",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "food_item_id",
            sa.Uuid(),
            sa.ForeignKey("food_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    conn = op.get_bind()

    # 3) Seed: enstaka pass
    exercise_ids = {
        row[1]: UUID(str(row[0]).replace("-", ""))
        for row in conn.execute(sa.text("SELECT id, name FROM exercises"))
    }
    programs_t = sa.table(
        "programs",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("level", sa.String()),
        sa.column("days_per_week", sa.Integer()),
        sa.column("kind", sa.String()),
    )
    days_t = sa.table(
        "program_days",
        sa.column("id", sa.Uuid()),
        sa.column("program_id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("position", sa.Integer()),
    )
    day_ex_t = sa.table(
        "program_day_exercises",
        sa.column("id", sa.Uuid()),
        sa.column("program_day_id", sa.Uuid()),
        sa.column("exercise_id", sa.Uuid()),
        sa.column("position", sa.Integer()),
        sa.column("target_sets", sa.Integer()),
        sa.column("target_reps", sa.String()),
        sa.column("rest_seconds", sa.Integer()),
    )

    program_rows, day_rows, day_ex_rows = [], [], []
    for name, description, level, exercises in SINGLE_WORKOUTS:
        pid = uuid4()
        program_rows.append(
            {
                "id": pid,
                "user_id": None,
                "name": name,
                "description": description,
                "level": level,
                "days_per_week": None,
                "kind": "single",
            }
        )
        did = uuid4()
        day_rows.append(
            {"id": did, "program_id": pid, "name": name, "position": 0}
        )
        for pos, (ex_name, sets, reps, rest) in enumerate(exercises):
            if ex_name not in exercise_ids:  # robust mot namnändringar
                continue
            day_ex_rows.append(
                {
                    "id": uuid4(),
                    "program_day_id": did,
                    "exercise_id": exercise_ids[ex_name],
                    "position": pos,
                    "target_sets": sets,
                    "target_reps": reps,
                    "rest_seconds": rest,
                }
            )
    op.bulk_insert(programs_t, program_rows)
    op.bulk_insert(days_t, day_rows)
    op.bulk_insert(day_ex_t, day_ex_rows)

    # 4) Seed: basförslag i livsmedelsbiblioteket
    foods_t = sa.table(
        "food_items",
        sa.column("id", sa.Uuid()),
        sa.column("barcode", sa.String()),
        sa.column("name", sa.String()),
        sa.column("brand", sa.String()),
        sa.column("source", sa.String()),
        sa.column("per_100g", sa.JSON()),
        sa.column("created_by", sa.Uuid()),
    )
    food_rows = []
    for name, kcal, protein, carbs, fat, fiber in BASE_FOODS:
        per = {
            "kcal": kcal,
            "protein_g": protein,
            "carbs_g": carbs,
            "fat_g": fat,
        }
        if fiber is not None:
            per["fiber_g"] = fiber
        food_rows.append(
            {
                "id": uuid4(),
                "barcode": None,
                "name": name,
                "brand": None,
                "source": "base",
                "per_100g": per,
                "created_by": None,
            }
        )
    op.bulk_insert(foods_t, food_rows)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM food_items WHERE source = 'base'"))
    for name, *_ in SINGLE_WORKOUTS:
        op.execute(
            sa.text(
                "DELETE FROM programs WHERE user_id IS NULL AND name = :name"
            ).bindparams(name=name)
        )
    op.drop_table("food_favorites")
    op.drop_column("programs", "kind")
