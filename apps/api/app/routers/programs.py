import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import Program, ProgramDay, ProgramDayExercise, User, UserProgram
from app.schemas_training import ProgramCreate, ProgramOut, UserProgramOut

router = APIRouter(prefix="/api/programs", tags=["programs"])


def _serialize(program: Program) -> ProgramOut:
    out = ProgramOut.model_validate(program)
    out.is_global = program.user_id is None
    return out


async def _get_visible_program(
    program_id: uuid.UUID, user: User, session: AsyncSession
) -> Program:
    program = await session.get(Program, program_id)
    if program is None or (program.user_id is not None and program.user_id != user.id):
        raise HTTPException(404, "Programmet finns inte.")
    return program


@router.get("", response_model=list[ProgramOut])
async def list_programs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ProgramOut]:
    result = await session.scalars(
        select(Program)
        .where(or_(Program.user_id.is_(None), Program.user_id == user.id))
        .order_by(Program.name)
    )
    return [_serialize(p) for p in result]


@router.get("/{program_id}", response_model=ProgramOut)
async def get_program(
    program_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProgramOut:
    return _serialize(await _get_visible_program(program_id, user, session))


@router.post("", response_model=ProgramOut, status_code=201)
async def create_program(
    payload: ProgramCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ProgramOut:
    program = Program(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        level=payload.level,
        days_per_week=payload.days_per_week,
    )
    for day_pos, day in enumerate(payload.days):
        program_day = ProgramDay(name=day.name, position=day_pos)
        for ex_pos, ex in enumerate(day.exercises):
            program_day.exercises.append(
                ProgramDayExercise(
                    exercise_id=ex.exercise_id,
                    position=ex_pos,
                    target_sets=ex.target_sets,
                    target_reps=ex.target_reps,
                    rest_seconds=ex.rest_seconds,
                    notes=ex.notes,
                )
            )
        program.days.append(program_day)
    session.add(program)
    await session.commit()
    # Ladda om med eager-relationer (async-säkert efter commit)
    program = await session.scalar(
        select(Program)
        .where(Program.id == program.id)
        .execution_options(populate_existing=True)
    )
    return _serialize(program)


@router.delete("/{program_id}", status_code=204)
async def delete_program(
    program_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    program = await session.get(Program, program_id)
    if program is None or program.user_id != user.id:
        raise HTTPException(404, "Programmet finns inte.")
    await session.delete(program)
    await session.commit()


@router.post("/{program_id}/activate", response_model=UserProgramOut)
async def activate_program(
    program_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserProgram:
    program = await _get_visible_program(program_id, user, session)
    if not program.days:
        raise HTTPException(400, "Programmet har inga träningsdagar.")

    existing = list(
        await session.scalars(
            select(UserProgram).where(UserProgram.user_id == user.id)
        )
    )
    target = None
    for up in existing:
        if up.program_id == program.id:
            up.is_active = True
            target = up  # återupptas där man var i rotationen
        else:
            up.is_active = False
    if target is None:
        target = UserProgram(user_id=user.id, program_id=program.id)
        session.add(target)

    await session.commit()
    # Ladda om med eager-relationer (async-säkert efter commit)
    return await session.scalar(
        select(UserProgram)
        .where(UserProgram.id == target.id)
        .execution_options(populate_existing=True)
    )


active_router = APIRouter(prefix="/api/user-programs", tags=["programs"])


@active_router.get("/active", response_model=UserProgramOut | None)
async def get_active_program(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> UserProgram | None:
    return await session.scalar(
        select(UserProgram).where(
            UserProgram.user_id == user.id, UserProgram.is_active.is_(True)
        )
    )
