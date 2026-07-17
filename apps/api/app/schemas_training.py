import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Övningar ──────────────────────────────────────────────────


class ExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    muscle_groups: list[str]
    equipment: list[str]
    is_global: bool


class ExerciseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    muscle_groups: list[str] = []
    equipment: list[str] = []


# ── Program ───────────────────────────────────────────────────


class ProgramDayExerciseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise: ExerciseOut
    position: int
    target_sets: int
    target_reps: str
    rest_seconds: int
    notes: str | None


class ProgramDayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    position: int
    exercises: list[ProgramDayExerciseOut]


class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    level: str
    days_per_week: int | None
    kind: str = "program"  # program = rotation, single = fristående pass
    is_global: bool = False
    days: list[ProgramDayOut]


class ProgramDayExerciseCreate(BaseModel):
    exercise_id: uuid.UUID
    target_sets: int = Field(default=3, ge=1, le=20)
    target_reps: str = Field(default="8-12", max_length=20)
    rest_seconds: int = Field(default=90, ge=0, le=1800)
    notes: str | None = None


class ProgramDayCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    exercises: list[ProgramDayExerciseCreate] = []


class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    level: str = Field(default="beginner", pattern="^(beginner|intermediate|advanced)$")
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    days: list[ProgramDayCreate] = Field(min_length=1)


class UserProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    program: ProgramOut
    started_at: datetime
    next_day_position: int
    is_active: bool


# ── Pass & set ────────────────────────────────────────────────


class SetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    exercise_id: uuid.UUID
    set_number: int
    weight_kg: float | None
    reps: int
    rpe: float | None
    is_warmup: bool


class SetCreate(BaseModel):
    exercise_id: uuid.UUID
    weight_kg: float | None = Field(default=None, ge=0, le=2000)
    reps: int = Field(ge=0, le=1000)
    rpe: float | None = Field(default=None, ge=1, le=10)
    is_warmup: bool = False


class PreviousSets(BaseModel):
    """Föregående prestation för en övning — visas inline vid inmatning."""

    performed_at: datetime
    sets: list[SetOut]


class SessionExercisePlan(BaseModel):
    exercise: ExerciseOut
    target_sets: int | None = None
    target_reps: str | None = None
    rest_seconds: int | None = None
    notes: str | None = None
    previous: PreviousSets | None = None


class SessionStart(BaseModel):
    program_day_id: uuid.UUID | None = None


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    notes: str | None
    day_name: str | None = None
    program_name: str | None = None
    set_count: int = 0
    total_volume_kg: float = 0


class SessionDetail(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    notes: str | None
    day_name: str | None
    program_name: str | None
    plan: list[SessionExercisePlan]
    sets: list[SetOut]


class SessionFinish(BaseModel):
    notes: str | None = None
