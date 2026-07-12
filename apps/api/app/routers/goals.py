import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import (
    METRICS,
    BodyMetric,
    CardioActivity,
    Goal,
    User,
    WorkoutSession,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


class GoalCreate(BaseModel):
    kind: str = Field(pattern="^(pace_distance|body_metric|frequency)$")
    title: str = Field(min_length=1, max_length=200)
    target: dict
    deadline: date | None = None


class GoalOut(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    target: dict
    deadline: date | None
    achieved_at: datetime | None
    created_at: datetime
    progress: float  # 0..1
    current: dict  # nulägesdata för visning


async def _latest_metric(
    db: AsyncSession, user: User, metric: str
) -> float | None:
    row = await db.scalar(
        select(BodyMetric)
        .where(BodyMetric.user_id == user.id, BodyMetric.metric == metric)
        .order_by(BodyMetric.measured_at.desc())
        .limit(1)
    )
    return float(row.value) if row else None


async def _progress(goal: Goal, user: User, db: AsyncSession) -> tuple[float, dict]:
    target = goal.target or {}

    if goal.kind == "body_metric":
        metric = target.get("metric")
        goal_value = float(target.get("value", 0))
        baseline = target.get("baseline")
        current = await _latest_metric(db, user, metric) if metric else None
        if current is None or baseline is None:
            return 0.0, {"current_value": current}
        baseline = float(baseline)
        span = baseline - goal_value
        if abs(span) < 1e-9:
            progress = 1.0 if current == goal_value else 0.0
        else:
            progress = (baseline - current) / span
        return max(0.0, min(1.0, progress)), {
            "current_value": current,
            "baseline": baseline,
        }

    if goal.kind == "pace_distance":
        distance_m = float(target.get("distance_m", 0))
        time_s = float(target.get("time_s", 0))
        if distance_m <= 0 or time_s <= 0:
            return 0.0, {}
        # Bästa uppskattade tid för måldistansen bland löprundor som är
        # minst 95 % av distansen (skalat via snittempo).
        rows = list(
            await db.scalars(
                select(CardioActivity).where(
                    CardioActivity.user_id == user.id,
                    CardioActivity.type == "run",
                    CardioActivity.distance_m >= distance_m * 0.95,
                    CardioActivity.avg_pace_s_per_km.is_not(None),
                )
            )
        )
        if not rows:
            return 0.0, {"best_time_s": None}
        best = min(float(r.avg_pace_s_per_km) * distance_m / 1000 for r in rows)
        return min(1.0, time_s / best), {"best_time_s": round(best)}

    if goal.kind == "frequency":
        per_week = int(target.get("sessions_per_week", 0))
        if per_week <= 0:
            return 0.0, {}
        week_start = datetime.now(timezone.utc) - timedelta(
            days=datetime.now(timezone.utc).weekday()
        )
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        strength = await db.scalar(
            select(func.count(WorkoutSession.id)).where(
                WorkoutSession.user_id == user.id,
                WorkoutSession.finished_at.is_not(None),
                WorkoutSession.started_at >= week_start,
            )
        )
        cardio = await db.scalar(
            select(func.count(CardioActivity.id)).where(
                CardioActivity.user_id == user.id,
                CardioActivity.started_at >= week_start,
            )
        )
        done = (strength or 0) + (cardio or 0)
        return min(1.0, done / per_week), {"sessions_this_week": done}

    return 0.0, {}


async def _to_out(goal: Goal, user: User, db: AsyncSession) -> GoalOut:
    progress, current = await _progress(goal, user, db)
    if progress >= 1.0 and goal.achieved_at is None:
        goal.achieved_at = datetime.now(timezone.utc)
        await db.commit()
    return GoalOut(
        id=goal.id,
        kind=goal.kind,
        title=goal.title,
        target=goal.target,
        deadline=goal.deadline,
        achieved_at=goal.achieved_at,
        created_at=goal.created_at,
        progress=round(progress, 3),
        current=current,
    )


@router.get("", response_model=list[GoalOut])
async def list_goals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[GoalOut]:
    goals = list(
        await db.scalars(
            select(Goal)
            .where(Goal.user_id == user.id)
            .order_by(Goal.created_at.desc())
        )
    )
    return [await _to_out(g, user, db) for g in goals]


@router.post("", response_model=GoalOut, status_code=201)
async def create_goal(
    payload: GoalCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> GoalOut:
    target = dict(payload.target)

    if payload.kind == "body_metric":
        metric = target.get("metric")
        if metric not in METRICS:
            raise HTTPException(400, "Okänt mätetal i målet.")
        if "value" not in target:
            raise HTTPException(400, "Målet saknar 'value'.")
        # Lås baseline = senaste mätningen när målet skapas
        if target.get("baseline") is None:
            baseline = await _latest_metric(db, user, metric)
            if baseline is None:
                raise HTTPException(
                    400,
                    "Ingen mätning finns för mätetalet ännu — logga eller "
                    "synka en första mätning innan målet skapas.",
                )
            target["baseline"] = baseline
    elif payload.kind == "pace_distance":
        if not target.get("distance_m") or not target.get("time_s"):
            raise HTTPException(400, "Målet kräver distance_m och time_s.")
    elif payload.kind == "frequency":
        if not target.get("sessions_per_week"):
            raise HTTPException(400, "Målet kräver sessions_per_week.")

    goal = Goal(
        user_id=user.id,
        kind=payload.kind,
        title=payload.title,
        target=target,
        deadline=payload.deadline,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return await _to_out(goal, user, db)


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    goal = await db.get(Goal, goal_id)
    if goal is None or goal.user_id != user.id:
        raise HTTPException(404, "Målet finns inte.")
    await db.delete(goal)
    await db.commit()
