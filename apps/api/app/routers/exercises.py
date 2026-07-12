from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Exercise, User
from app.schemas_training import ExerciseCreate, ExerciseOut

router = APIRouter(prefix="/api/exercises", tags=["exercises"])


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
        is_global=False,
        created_by=user.id,
    )
    session.add(exercise)
    await session.commit()
    await session.refresh(exercise)
    return exercise
