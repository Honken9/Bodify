import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    CardioActivity,
    Exercise,
    ProgramDay,
    User,
    UserProgram,
    WorkoutSession,
    WorkoutSet,
)
from app.schemas_training import (
    ExerciseOut,
    PreviousSets,
    SessionDetail,
    SessionExercisePlan,
    SessionFinish,
    SessionStart,
    SessionSummary,
    SetCreate,
    SetOut,
    WatchData,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _get_own_session(
    session_id: uuid.UUID, user: User, db: AsyncSession
) -> WorkoutSession:
    ws = await db.get(WorkoutSession, session_id)
    if ws is None or ws.user_id != user.id:
        raise HTTPException(404, "Passet finns inte.")
    return ws


async def _previous_sets(
    db: AsyncSession,
    user: User,
    exercise_id: uuid.UUID,
    exclude_session_id: uuid.UUID | None,
) -> PreviousSets | None:
    """Senaste avslutade passet där övningen förekom — vikt/reps visas
    inline vid inmatning så progressiv överbelastning blir självklar."""
    stmt = (
        select(WorkoutSession)
        .join(WorkoutSet, WorkoutSet.session_id == WorkoutSession.id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.finished_at.is_not(None),
            WorkoutSet.exercise_id == exercise_id,
        )
        .order_by(WorkoutSession.started_at.desc())
        .limit(1)
    )
    if exclude_session_id is not None:
        stmt = stmt.where(WorkoutSession.id != exclude_session_id)
    last_session = await db.scalar(stmt)
    if last_session is None:
        return None

    sets = await db.scalars(
        select(WorkoutSet)
        .where(
            WorkoutSet.session_id == last_session.id,
            WorkoutSet.exercise_id == exercise_id,
        )
        .order_by(WorkoutSet.set_number)
    )
    return PreviousSets(
        performed_at=last_session.started_at,
        sets=[SetOut.model_validate(s) for s in sets],
    )


def _watch_data(activity: CardioActivity | None) -> WatchData | None:
    if activity is None:
        return None
    return WatchData(
        activity_id=activity.id,
        source=activity.source,
        duration_s=activity.duration_s,
        avg_hr=float(activity.avg_hr) if activity.avg_hr else None,
        max_hr=float(activity.max_hr) if activity.max_hr else None,
        calories=float(activity.calories) if activity.calories else None,
    )


async def _build_detail(
    ws: WorkoutSession, user: User, db: AsyncSession
) -> SessionDetail:
    plan: list[SessionExercisePlan] = []
    planned_ids: set[uuid.UUID] = set()

    if ws.program_day is not None:
        for pde in ws.program_day.exercises:
            planned_ids.add(pde.exercise_id)
            plan.append(
                SessionExercisePlan(
                    exercise=ExerciseOut.model_validate(pde.exercise),
                    target_sets=pde.target_sets,
                    target_reps=pde.target_reps,
                    rest_seconds=pde.rest_seconds,
                    notes=pde.notes,
                    previous=await _previous_sets(db, user, pde.exercise_id, ws.id),
                )
            )

    # Övningar som lagts till ad hoc under passet (utanför dagens plan)
    extra_ids = {s.exercise_id for s in ws.sets} - planned_ids
    for ex_id in extra_ids:
        exercise = await db.get(Exercise, ex_id)
        if exercise is None:
            continue
        plan.append(
            SessionExercisePlan(
                exercise=ExerciseOut.model_validate(exercise),
                previous=await _previous_sets(db, user, ex_id, ws.id),
            )
        )

    linked = await db.scalar(
        select(CardioActivity).where(CardioActivity.linked_session_id == ws.id)
    )
    return SessionDetail(
        id=ws.id,
        started_at=ws.started_at,
        finished_at=ws.finished_at,
        notes=ws.notes,
        day_name=ws.program_day.name if ws.program_day else None,
        program_name=ws.program_day.program.name if ws.program_day else None,
        plan=plan,
        sets=[SetOut.model_validate(s) for s in ws.sets],
        watch=_watch_data(linked),
    )


@router.post("/start", response_model=SessionDetail, status_code=201)
async def start_session(
    payload: SessionStart,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SessionDetail:
    program_day_id = payload.program_day_id
    if program_day_id is not None:
        day = await db.get(ProgramDay, program_day_id)
        if day is None:
            raise HTTPException(404, "Träningsdagen finns inte.")
        program = day.program
        if program.user_id is not None and program.user_id != user.id:
            raise HTTPException(404, "Träningsdagen finns inte.")

    ws = WorkoutSession(
        user_id=user.id,
        program_day_id=program_day_id,
        start_lat=payload.lat,
        start_lng=payload.lng,
    )
    db.add(ws)
    await db.commit()
    # Ladda om med eager-relationer (async-säkert efter commit)
    ws = await db.scalar(
        select(WorkoutSession)
        .where(WorkoutSession.id == ws.id)
        .execution_options(populate_existing=True)
    )
    return await _build_detail(ws, user, db)


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = 30,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[SessionSummary]:
    sessions = list(
        await db.scalars(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == user.id)
            .order_by(WorkoutSession.started_at.desc())
            .limit(min(limit, 100))
            .offset(offset)
        )
    )
    if not sessions:
        return []

    volume_rows = await db.execute(
        select(
            WorkoutSet.session_id,
            func.count(WorkoutSet.id),
            func.coalesce(
                func.sum(WorkoutSet.weight_kg * WorkoutSet.reps), 0
            ),
        )
        .where(WorkoutSet.session_id.in_([s.id for s in sessions]))
        .where(WorkoutSet.is_warmup.is_(False))
        .group_by(WorkoutSet.session_id)
    )
    stats = {row[0]: (row[1], float(row[2])) for row in volume_rows}

    linked_map = {
        a.linked_session_id: a
        for a in await db.scalars(
            select(CardioActivity).where(
                CardioActivity.linked_session_id.in_([s.id for s in sessions])
            )
        )
    }

    return [
        SessionSummary(
            id=s.id,
            started_at=s.started_at,
            finished_at=s.finished_at,
            notes=s.notes,
            day_name=s.program_day.name if s.program_day else None,
            program_name=s.program_day.program.name if s.program_day else None,
            set_count=stats.get(s.id, (0, 0.0))[0],
            total_volume_kg=stats.get(s.id, (0, 0.0))[1],
            watch=_watch_data(linked_map.get(s.id)),
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session_detail(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SessionDetail:
    ws = await _get_own_session(session_id, user, db)
    return await _build_detail(ws, user, db)


@router.post("/{session_id}/sets", response_model=SetOut, status_code=201)
async def add_set(
    session_id: uuid.UUID,
    payload: SetCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> WorkoutSet:
    ws = await _get_own_session(session_id, user, db)
    if ws.finished_at is not None:
        raise HTTPException(409, "Passet är redan avslutat.")

    exercise = await db.get(Exercise, payload.exercise_id)
    if exercise is None or (
        not exercise.is_global and exercise.created_by != user.id
    ):
        raise HTTPException(404, "Övningen finns inte.")

    next_number = (
        await db.scalar(
            select(func.coalesce(func.max(WorkoutSet.set_number), 0)).where(
                WorkoutSet.session_id == ws.id,
                WorkoutSet.exercise_id == payload.exercise_id,
            )
        )
    ) + 1

    workout_set = WorkoutSet(
        session_id=ws.id,
        exercise_id=payload.exercise_id,
        set_number=next_number,
        weight_kg=payload.weight_kg,
        reps=payload.reps,
        rpe=payload.rpe,
        is_warmup=payload.is_warmup,
    )
    db.add(workout_set)
    await db.commit()
    await db.refresh(workout_set)
    return workout_set


@router.delete("/{session_id}/sets/{set_id}", status_code=204)
async def delete_set(
    session_id: uuid.UUID,
    set_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    ws = await _get_own_session(session_id, user, db)
    workout_set = await db.get(WorkoutSet, set_id)
    if workout_set is None or workout_set.session_id != ws.id:
        raise HTTPException(404, "Setet finns inte.")
    await db.delete(workout_set)
    await db.commit()


@router.post("/{session_id}/finish", response_model=SessionDetail)
async def finish_session(
    session_id: uuid.UUID,
    payload: SessionFinish,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SessionDetail:
    ws = await _get_own_session(session_id, user, db)
    if ws.finished_at is not None:
        raise HTTPException(409, "Passet är redan avslutat.")

    ws.finished_at = datetime.now(timezone.utc)
    if payload.notes:
        ws.notes = payload.notes

    # Rullande split: flytta pekaren till nästa dag i det aktiva programmet.
    if ws.program_day is not None:
        active = await db.scalar(
            select(UserProgram).where(
                UserProgram.user_id == user.id,
                UserProgram.program_id == ws.program_day.program_id,
                UserProgram.is_active.is_(True),
            )
        )
        if active is not None:
            day_count = len(ws.program_day.program.days)
            if day_count > 0:
                active.next_day_position = (
                    ws.program_day.position + 1
                ) % day_count

    await db.commit()
    await db.refresh(ws)

    # Fanns ett klockinspelat gympass med samma starttid? Slå ihop direkt.
    from app.services.watch_link import autolink_watch_activities

    await autolink_watch_activities(db, user)
    return await _build_detail(ws, user, db)


@router.post("/{session_id}/unlink-watch", response_model=SessionDetail)
async def unlink_watch(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> SessionDetail:
    """Koppla isär klockpasset från styrkepasset — klockans version blir
    ett eget pass igen och länkas aldrig om automatiskt."""
    ws = await _get_own_session(session_id, user, db)
    activity = await db.scalar(
        select(CardioActivity).where(CardioActivity.linked_session_id == ws.id)
    )
    if activity is None:
        raise HTTPException(404, "Inget klockpass är kopplat till passet.")
    activity.linked_session_id = None
    activity.autolink_opt_out = True
    await db.commit()
    return await _build_detail(ws, user, db)
