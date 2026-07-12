"""Fler färdiga program för alla nivåer

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-12

"""
from uuid import UUID, uuid4

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# (namn, beskrivning, nivå, dagar/vecka, [(dagnamn, [(övning, set, reps, vila)])])
PROGRAMS = [
    (
        "Kroppsvikt hemma A/B",
        "Ingen utrustning alls — två rullande pass för vardagsrummet, "
        "hotellrummet eller semestern.",
        "beginner",
        3,
        [
            (
                "Hemmapass A",
                [
                    ("Armhävningar", 3, "10-20", 60),
                    ("Sit-ups", 3, "15-20", 45),
                    ("Plankan", 3, "30-60 s", 60),
                    ("Burpees", 3, "10-15", 90),
                ],
            ),
            (
                "Hemmapass B",
                [
                    ("Bänkdips", 3, "10-15", 60),
                    ("Russian twists", 3, "20", 45),
                    ("Sidoplanka", 3, "30 s/sida", 60),
                    ("Burpees", 3, "10-15", 90),
                ],
            ),
        ],
    ),
    (
        "5×5 Styrka A/B",
        "Klassiskt styrkeprogram med fokus på baslyften. Kör 3 pass i "
        "veckan så rullar A och B automatiskt.",
        "intermediate",
        3,
        [
            (
                "5×5 Pass A",
                [
                    ("Knäböj", 5, "5", 180),
                    ("Bänkpress", 5, "5", 180),
                    ("Skivstångsrodd", 5, "5", 150),
                ],
            ),
            (
                "5×5 Pass B",
                [
                    ("Knäböj", 5, "5", 180),
                    ("Militärpress", 5, "5", 180),
                    ("Marklyft", 1, "5", 240),
                ],
            ),
        ],
    ),
    (
        "Push/Pull/Legs (6 dagar)",
        "Klassisk PPL-rotation för dig som tränar ofta — tre pass som "
        "rullar två varv i veckan.",
        "advanced",
        6,
        [
            (
                "Push",
                [
                    ("Bänkpress", 4, "6-8", 150),
                    ("Militärpress", 3, "8-10", 120),
                    ("Lutande hantelpress", 3, "8-12", 90),
                    ("Sidolyft", 3, "12-15", 60),
                    ("Pushdowns", 3, "10-12", 60),
                ],
            ),
            (
                "Pull",
                [
                    ("Marklyft", 3, "5", 210),
                    ("Pull-ups", 4, "max", 120),
                    ("Sittande kabelrodd", 3, "8-10", 90),
                    ("Face pulls", 3, "12-15", 60),
                    ("Hantelcurl", 3, "10-12", 60),
                ],
            ),
            (
                "Legs",
                [
                    ("Knäböj", 4, "6-8", 180),
                    ("Rumänska marklyft", 3, "8-10", 150),
                    ("Benspark", 3, "10-12", 90),
                    ("Liggande lårcurl", 3, "10-12", 90),
                    ("Stående vadpress", 4, "12-15", 60),
                ],
            ),
        ],
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    exercise_ids = {
        # rå-SELECT ger hexsträng på SQLite, UUID-objekt på Postgres —
        # normalisera så bulk_insert alltid får uuid.UUID
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
    for name, description, level, days_per_week, days in PROGRAMS:
        pid = uuid4()
        program_rows.append(
            {
                "id": pid,
                "user_id": None,
                "name": name,
                "description": description,
                "level": level,
                "days_per_week": days_per_week,
            }
        )
        for day_pos, (day_name, day_exercises) in enumerate(days):
            did = uuid4()
            day_rows.append(
                {"id": did, "program_id": pid, "name": day_name, "position": day_pos}
            )
            for ex_pos, (ex_name, sets, reps, rest) in enumerate(day_exercises):
                if ex_name not in exercise_ids:  # robust mot namnändringar
                    continue
                day_ex_rows.append(
                    {
                        "id": uuid4(),
                        "program_day_id": did,
                        "exercise_id": exercise_ids[ex_name],
                        "position": ex_pos,
                        "target_sets": sets,
                        "target_reps": reps,
                        "rest_seconds": rest,
                    }
                )
    op.bulk_insert(programs_t, program_rows)
    op.bulk_insert(days_t, day_rows)
    op.bulk_insert(day_ex_t, day_ex_rows)


def downgrade() -> None:
    for name, *_ in PROGRAMS:
        op.execute(
            sa.text(
                "DELETE FROM programs WHERE user_id IS NULL AND name = :name"
            ).bindparams(name=name)
        )
