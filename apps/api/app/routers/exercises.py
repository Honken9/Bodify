import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Exercise, User, WorkoutSession, WorkoutSet
from app.schemas_training import ExerciseCreate, ExerciseOut

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


def _est_1rm(weight: float, reps: int) -> float:
    """Epley-formeln — uppskattat 1RM ur vikt × reps."""
    if reps <= 1:
        return weight
    return weight * (1 + reps / 30)


@router.get("", response_model=list[ExerciseOut])
async def list_exercises(
    search: str | None = None,
    muscle: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Exercise]:
    stmt = select(Exercise).where(
        or_(Exercise.is_global.is_(True), Exercise.created_by == user.id)
    )
    if search:
        stmt = stmt.where(Exercise.name.ilike(f"%{search}%"))
    result = await session.scalars(stmt.order_by(Exercise.name))
    exercises = list(result)
    if muscle:
        # muskelgrupper lagras som JSON-lista; filtrera i Python för
        # dialektoberoende (SQLite i test, Postgres i drift)
        exercises = [e for e in exercises if muscle in e.muscle_groups]
    return exercises


@router.get("/{exercise_id}/progression")
async def exercise_progression(
    exercise_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Utveckling per pass: tyngsta set, uppskattat 1RM (Epley) och volym
    — plus personbästa. Driver progressionsgrafen och PB-raden."""
    exercise = await session.get(Exercise, exercise_id)
    if exercise is None or (
        not exercise.is_global and exercise.created_by != user.id
    ):
        raise HTTPException(404, "Övningen finns inte.")

    rows = await session.execute(
        select(
            WorkoutSession.id,
            WorkoutSession.started_at,
            WorkoutSet.weight_kg,
            WorkoutSet.reps,
        )
        .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSet.exercise_id == exercise_id,
            WorkoutSet.is_warmup.is_(False),
        )
        .order_by(WorkoutSession.started_at)
    )

    per_session: dict = {}
    for session_id, started_at, weight, reps in rows:
        entry = per_session.setdefault(
            session_id,
            {"day": started_at.date().isoformat(), "best_weight": 0.0, "est_1rm": 0.0, "volume": 0.0},
        )
        w = float(weight) if weight is not None else 0.0
        entry["best_weight"] = max(entry["best_weight"], w)
        entry["est_1rm"] = max(entry["est_1rm"], round(_est_1rm(w, int(reps)), 1))
        entry["volume"] += w * int(reps)

    points = list(per_session.values())
    records = {
        "best_weight": max((p["best_weight"] for p in points), default=0),
        "best_1rm": max((p["est_1rm"] for p in points), default=0),
        "best_volume": round(max((p["volume"] for p in points), default=0)),
        "sessions": len(points),
    }
    return {"points": points, "records": records}


@router.post("", response_model=ExerciseOut, status_code=201)
async def create_exercise(
    payload: ExerciseCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Exercise:
    exercise = Exercise(
        name=payload.name,
        muscle_groups=payload.muscle_groups,
        equipment=payload.equipment,
        description=payload.description,
        is_global=False,
        created_by=user.id,
    )
    session.add(exercise)
    await session.commit()
    await session.refresh(exercise)
    return exercise
