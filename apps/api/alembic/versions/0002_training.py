"""Träningsloggbok: övningar, program, pass, set + seed-data

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, index=True),
        sa.Column("muscle_groups", sa.JSON(), nullable=False),
        sa.Column("equipment", sa.JSON(), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_table(
        "programs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("level", sa.String(20), nullable=False, server_default="beginner"),
        sa.Column("days_per_week", sa.Integer(), nullable=True),
    )
    op.create_table(
        "program_days",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Uuid(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_table(
        "program_day_exercises",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "program_day_id",
            sa.Uuid(),
            sa.ForeignKey("program_days.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "exercise_id",
            sa.Uuid(),
            sa.ForeignKey("exercises.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("target_reps", sa.String(20), nullable=False, server_default="8-12"),
        sa.Column("rest_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "user_programs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "program_id",
            sa.Uuid(),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("next_day_position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "program_day_id",
            sa.Uuid(),
            sa.ForeignKey("program_days.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "workout_sets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "session_id",
            sa.Uuid(),
            sa.ForeignKey("workout_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "exercise_id",
            sa.Uuid(),
            sa.ForeignKey("exercises.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("set_number", sa.Integer(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(6, 2), nullable=True),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("rpe", sa.Numeric(3, 1), nullable=True),
        sa.Column("is_warmup", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    _seed()

    # RLS-grund: policies aktiveras nu, men appen ansluter i dagsläget som
    # tabellägare (som inte omfattas av RLS utan FORCE). Fullt genomslag får
    # skyddet när en dedikerad, icke-ägande approll införs. App-lagret
    # filtrerar alltid explicit på user_id — RLS är hängslen och livrem.
    if op.get_bind().dialect.name == "postgresql":
        uid = "current_setting('app.user_id', true)::uuid"
        op.execute("ALTER TABLE exercises ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant ON exercises USING (is_global OR created_by = {uid})"
        )
        op.execute("ALTER TABLE programs ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant ON programs USING (user_id IS NULL OR user_id = {uid})"
        )
        op.execute("ALTER TABLE program_days ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant ON program_days USING (EXISTS ("
            "SELECT 1 FROM programs p WHERE p.id = program_id "
            f"AND (p.user_id IS NULL OR p.user_id = {uid})))"
        )
        op.execute("ALTER TABLE program_day_exercises ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant ON program_day_exercises USING (EXISTS ("
            "SELECT 1 FROM program_days d JOIN programs p ON p.id = d.program_id "
            "WHERE d.id = program_day_id "
            f"AND (p.user_id IS NULL OR p.user_id = {uid})))"
        )
        op.execute("ALTER TABLE user_programs ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON user_programs USING (user_id = {uid})")
        op.execute("ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant ON workout_sessions USING (user_id = {uid})")
        op.execute("ALTER TABLE workout_sets ENABLE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY tenant ON workout_sets USING (EXISTS ("
            "SELECT 1 FROM workout_sessions ws WHERE ws.id = session_id "
            f"AND ws.user_id = {uid}))"
        )


def downgrade() -> None:
    for table in (
        "workout_sets",
        "workout_sessions",
        "user_programs",
        "program_day_exercises",
        "program_days",
        "programs",
        "exercises",
    ):
        op.drop_table(table)


# ── Seed-data ─────────────────────────────────────────────────

# (namn, muskelgrupper, utrustning)
EXERCISES: list[tuple[str, list[str], list[str]]] = [
    # Bröst
    ("Bänkpress", ["bröst", "triceps"], ["skivstång"]),
    ("Lutande bänkpress", ["bröst", "axlar", "triceps"], ["skivstång"]),
    ("Hantelpress", ["bröst", "triceps"], ["hantlar"]),
    ("Lutande hantelpress", ["bröst", "axlar"], ["hantlar"]),
    ("Flyes med hantlar", ["bröst"], ["hantlar"]),
    ("Kabelflyes", ["bröst"], ["kabel"]),
    ("Armhävningar", ["bröst", "triceps", "mage"], ["kroppsvikt"]),
    ("Dips", ["bröst", "triceps"], ["kroppsvikt"]),
    ("Bröstpress i maskin", ["bröst"], ["maskin"]),
    ("Pec deck", ["bröst"], ["maskin"]),
    # Rygg
    ("Marklyft", ["rygg", "baksida lår", "säte"], ["skivstång"]),
    ("Rumänska marklyft", ["baksida lår", "säte", "ländrygg"], ["skivstång"]),
    ("Skivstångsrodd", ["rygg", "biceps"], ["skivstång"]),
    ("Hantelrodd", ["rygg", "biceps"], ["hantlar"]),
    ("Sittande kabelrodd", ["rygg", "biceps"], ["kabel"]),
    ("Latsdrag", ["rygg", "biceps"], ["maskin"]),
    ("Pull-ups", ["rygg", "biceps"], ["kroppsvikt"]),
    ("Chins", ["rygg", "biceps"], ["kroppsvikt"]),
    ("T-bar rodd", ["rygg"], ["skivstång"]),
    ("Face pulls", ["axlar", "rygg"], ["kabel"]),
    ("Hyperextensions", ["ländrygg", "säte"], ["kroppsvikt"]),
    ("Shrugs", ["traps"], ["hantlar"]),
    # Ben & säte
    ("Knäböj", ["ben", "säte"], ["skivstång"]),
    ("Frontböj", ["ben", "mage"], ["skivstång"]),
    ("Benpress", ["ben", "säte"], ["maskin"]),
    ("Utfall", ["ben", "säte"], ["hantlar"]),
    ("Gående utfall", ["ben", "säte"], ["hantlar"]),
    ("Bulgarska utfall", ["ben", "säte"], ["hantlar"]),
    ("Benspark", ["ben"], ["maskin"]),
    ("Liggande lårcurl", ["baksida lår"], ["maskin"]),
    ("Sittande lårcurl", ["baksida lår"], ["maskin"]),
    ("Stående vadpress", ["vader"], ["maskin"]),
    ("Sittande vadpress", ["vader"], ["maskin"]),
    ("Höftlyft", ["säte"], ["skivstång"]),
    ("Goblet squat", ["ben", "säte"], ["hantlar", "kettlebell"]),
    ("Step-ups", ["ben", "säte"], ["hantlar"]),
    # Axlar
    ("Militärpress", ["axlar", "triceps"], ["skivstång"]),
    ("Axelpress med hantlar", ["axlar"], ["hantlar"]),
    ("Arnoldpress", ["axlar"], ["hantlar"]),
    ("Sidolyft", ["axlar"], ["hantlar"]),
    ("Framlyft", ["axlar"], ["hantlar"]),
    ("Omvända flyes", ["axlar", "rygg"], ["hantlar"]),
    ("Sidolyft i kabel", ["axlar"], ["kabel"]),
    ("Push press", ["axlar", "triceps", "ben"], ["skivstång"]),
    # Biceps
    ("Bicepscurl med skivstång", ["biceps"], ["skivstång"]),
    ("Hantelcurl", ["biceps"], ["hantlar"]),
    ("Hammercurl", ["biceps", "underarmar"], ["hantlar"]),
    ("Predikatorcurl", ["biceps"], ["maskin"]),
    ("Kabelcurl", ["biceps"], ["kabel"]),
    # Triceps
    ("Pushdowns", ["triceps"], ["kabel"]),
    ("Fransk press", ["triceps"], ["skivstång"]),
    ("Tricepsextension över huvudet", ["triceps"], ["hantlar"]),
    ("Smal bänkpress", ["triceps", "bröst"], ["skivstång"]),
    ("Bänkdips", ["triceps"], ["kroppsvikt"]),
    # Mage & core
    ("Plankan", ["mage"], ["kroppsvikt"]),
    ("Sidoplanka", ["mage"], ["kroppsvikt"]),
    ("Sit-ups", ["mage"], ["kroppsvikt"]),
    ("Hängande benlyft", ["mage"], ["kroppsvikt"]),
    ("Cable crunch", ["mage"], ["kabel"]),
    ("Russian twists", ["mage"], ["kroppsvikt"]),
    ("Ab wheel", ["mage"], ["kroppsvikt"]),
    ("Pallof press", ["mage"], ["kabel"]),
    # Helkropp & kondition
    ("Kettlebell swings", ["helkropp", "säte"], ["kettlebell"]),
    ("Thrusters", ["helkropp"], ["skivstång"]),
    ("Burpees", ["helkropp"], ["kroppsvikt"]),
    ("Farmer's walk", ["helkropp", "underarmar"], ["hantlar"]),
    ("Clean & press", ["helkropp"], ["skivstång"]),
]

# (namn, beskrivning, nivå, dagar/vecka, [(dagnamn, [(övning, set, reps, vila)])])
PROGRAMS = [
    (
        "Helkropp A/B (rullande)",
        "Två helkroppspass som rullar — kör 2–3 pass i veckan så växlar "
        "appen automatiskt mellan A och B.",
        "beginner",
        3,
        [
            (
                "Pass A",
                [
                    ("Knäböj", 3, "8-10", 150),
                    ("Bänkpress", 3, "8-10", 150),
                    ("Skivstångsrodd", 3, "8-10", 120),
                    ("Plankan", 3, "30-60 s", 60),
                    ("Hantelcurl", 2, "10-12", 60),
                ],
            ),
            (
                "Pass B",
                [
                    ("Marklyft", 3, "5-8", 180),
                    ("Militärpress", 3, "8-10", 120),
                    ("Latsdrag", 3, "10-12", 90),
                    ("Utfall", 3, "10-12", 90),
                    ("Pushdowns", 2, "10-12", 60),
                ],
            ),
        ],
    ),
    (
        "4-dagarssplit Överkropp/Underkropp",
        "Klassisk 4-dagarssplit med två överkropps- och två underkroppspass "
        "som rullar vidare vecka efter vecka.",
        "intermediate",
        4,
        [
            (
                "Överkropp A",
                [
                    ("Bänkpress", 4, "6-8", 150),
                    ("Skivstångsrodd", 4, "6-8", 150),
                    ("Axelpress med hantlar", 3, "8-10", 90),
                    ("Latsdrag", 3, "8-10", 90),
                    ("Hantelcurl", 3, "10-12", 60),
                    ("Pushdowns", 3, "10-12", 60),
                ],
            ),
            (
                "Underkropp A",
                [
                    ("Knäböj", 4, "6-8", 180),
                    ("Rumänska marklyft", 3, "8-10", 150),
                    ("Benpress", 3, "10-12", 120),
                    ("Stående vadpress", 4, "10-15", 60),
                    ("Plankan", 3, "45 s", 60),
                ],
            ),
            (
                "Överkropp B",
                [
                    ("Lutande hantelpress", 4, "8-10", 120),
                    ("Pull-ups", 4, "max", 120),
                    ("Sittande kabelrodd", 3, "10-12", 90),
                    ("Sidolyft", 3, "12-15", 60),
                    ("Hammercurl", 3, "10-12", 60),
                    ("Fransk press", 3, "10-12", 60),
                ],
            ),
            (
                "Underkropp B",
                [
                    ("Marklyft", 4, "5", 180),
                    ("Bulgarska utfall", 3, "8-10", 120),
                    ("Liggande lårcurl", 3, "10-12", 90),
                    ("Höftlyft", 3, "8-10", 120),
                    ("Hängande benlyft", 3, "10-15", 60),
                ],
            ),
        ],
    ),
]


def _seed() -> None:
    exercises_t = sa.table(
        "exercises",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("muscle_groups", sa.JSON()),
        sa.column("equipment", sa.JSON()),
        sa.column("is_global", sa.Boolean()),
    )
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

    exercise_ids: dict[str, object] = {}
    exercise_rows = []
    for name, muscles, equipment in EXERCISES:
        eid = uuid4()
        exercise_ids[name] = eid
        exercise_rows.append(
            {
                "id": eid,
                "name": name,
                "muscle_groups": muscles,
                "equipment": equipment,
                "is_global": True,
            }
        )
    op.bulk_insert(exercises_t, exercise_rows)

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
