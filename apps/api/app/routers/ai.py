import base64
import json
import logging
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import ollama
from app.ai.ollama import AIUnavailable
from app.auth import get_current_user
from app.db import get_session
from app.models import Exercise, Program, ProgramDay, ProgramDayExercise, User
from app.services import readiness as readiness_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

EQUIPMENT_VOCAB = [
    "skivstång",
    "hantlar",
    "maskin",
    "kabel",
    "kroppsvikt",
    "kettlebell",
]


# ── Readiness-coach ───────────────────────────────────────────


@router.get("/readiness")
async def readiness(
    advice: bool = False,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    result = await readiness_service.compute_readiness(db, user.id)

    if advice and result["status"] != "unknown":
        # LLM:en formulerar bara rådet — beslutet är redan fattat av reglerna
        try:
            factors_text = "; ".join(
                f"{f['name']}: {f['status']} ({f['detail']})"
                for f in result["factors"]
            )
            text = await ollama.chat(
                f"Status: {result['status']}. Signaler: {factors_text}. "
                f"Grundråd: {result['recommendation']}",
                system=(
                    "Du är en varm men rak träningscoach. Formulera om "
                    "grundrådet till 2–3 meningar på svenska, anpassat till "
                    "signalerna. Hitta inte på data. Ingen inledning."
                ),
                timeout=30,
            )
            result["ai_advice"] = text.strip()
        except AIUnavailable:
            pass  # regelmotorns råd räcker gott
    return result


# ── Pass-generator ────────────────────────────────────────────


class GenerateRequest(BaseModel):
    minutes: int = Field(default=45, ge=10, le=180)
    equipment: list[str] = Field(default_factory=lambda: list(EQUIPMENT_VOCAB))
    focus: str | None = Field(default=None, max_length=60)


class PlannedExercise(BaseModel):
    exercise_id: str
    name: str
    sets: int
    reps: str
    rest_seconds: int


class GeneratedPlan(BaseModel):
    name: str
    exercises: list[PlannedExercise]


class _LLMExercise(BaseModel):
    name: str
    sets: int = Field(ge=1, le=10)
    reps: str = Field(max_length=20)
    rest_seconds: int = Field(ge=15, le=600)


class _LLMPlan(BaseModel):
    name: str = Field(max_length=120)
    exercises: list[_LLMExercise] = Field(min_length=2, max_length=12)


async def _recent_volume(db: AsyncSession, user: User) -> str:
    from datetime import datetime, timedelta, timezone

    from app.models import WorkoutSession, WorkoutSet

    since = datetime.now(timezone.utc) - timedelta(days=7)
    rows = await db.execute(
        select(Exercise.muscle_groups, WorkoutSet.reps)
        .join(WorkoutSet, WorkoutSet.exercise_id == Exercise.id)
        .join(WorkoutSession, WorkoutSession.id == WorkoutSet.session_id)
        .where(
            WorkoutSession.user_id == user.id,
            WorkoutSession.started_at >= since,
        )
    )
    counts: dict[str, int] = {}
    for muscle_groups, _reps in rows:
        for m in muscle_groups or []:
            counts[m] = counts.get(m, 0) + 1
    if not counts:
        return "ingen träning senaste veckan"
    return ", ".join(f"{m}: {n} set" for m, n in sorted(counts.items()))


@router.post("/generate-workout", response_model=GeneratedPlan)
async def generate_workout(
    payload: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> GeneratedPlan:
    equipment = [e for e in payload.equipment if e in EQUIPMENT_VOCAB] or list(
        EQUIPMENT_VOCAB
    )
    exercises = list(
        await db.scalars(
            select(Exercise).where(
                or_(Exercise.is_global.is_(True), Exercise.created_by == user.id)
            )
        )
    )
    available = [
        e for e in exercises if any(eq in e.equipment for eq in equipment)
    ] or exercises
    by_name = {e.name.casefold(): e for e in available}

    volume = await _recent_volume(db, user)
    catalog = "\n".join(
        f"- {e.name} ({', '.join(e.muscle_groups)})" for e in available
    )
    prompt = (
        f"Skapa ett styrkepass på cirka {payload.minutes} minuter.\n"
        f"Tillgänglig utrustning: {', '.join(equipment)}.\n"
        f"Fokus: {payload.focus or 'helkropp/balanserat'}.\n"
        f"Senaste veckans volym per muskelgrupp: {volume} — "
        "prioritera det som fått minst.\n\n"
        "Välj ENDAST övningar från denna lista (exakta namn):\n"
        f"{catalog}\n\n"
        'Svara med strikt JSON: {"name": "passnamn", "exercises": '
        '[{"name": "...", "sets": 3, "reps": "8-12", "rest_seconds": 90}]}'
    )

    try:
        raw = await ollama.chat(prompt, json_format=True)
        plan = _LLMPlan.model_validate(json.loads(raw))
    except AIUnavailable as exc:
        raise HTTPException(
            503,
            "AI-tjänsten är inte igång. Starta Ollama: "
            "docker compose --profile ai up -d ollama",
        ) from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Ogiltigt AI-svar: %s", exc)
        raise HTTPException(502, "AI:n gav ett oanvändbart svar — försök igen.")

    resolved = []
    for item in plan.exercises:
        exercise = by_name.get(item.name.casefold())
        if exercise is None:
            continue  # hallucinerat namn — hoppa över
        resolved.append(
            PlannedExercise(
                exercise_id=str(exercise.id),
                name=exercise.name,
                sets=item.sets,
                reps=item.reps,
                rest_seconds=item.rest_seconds,
            )
        )
    if len(resolved) < 2:
        raise HTTPException(502, "AI:n gav ett oanvändbart svar — försök igen.")
    return GeneratedPlan(name=plan.name[:120], exercises=resolved)


class AcceptPlan(BaseModel):
    plan: GeneratedPlan


@router.post("/generate-workout/accept")
async def accept_generated_workout(
    payload: AcceptPlan,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Spara det genererade passet som ett eget enkeldagarsprogram och
    returnera dagens id — startas sedan som vanligt pass."""
    for item in payload.plan.exercises:
        exercise = await db.get(Exercise, uuid.UUID(item.exercise_id))
        if exercise is None or (
            not exercise.is_global and exercise.created_by != user.id
        ):
            raise HTTPException(404, f"Övningen '{item.name}' finns inte.")

    program = Program(
        user_id=user.id,
        name=f"✨ {payload.plan.name}"[:120],
        description="Genererat av Bodifys passgenerator.",
        level="intermediate",
    )
    day = ProgramDay(name=payload.plan.name[:120], position=0)
    for pos, item in enumerate(payload.plan.exercises):
        day.exercises.append(
            ProgramDayExercise(
                exercise_id=uuid.UUID(item.exercise_id),
                position=pos,
                target_sets=item.sets,
                target_reps=item.reps,
                rest_seconds=item.rest_seconds,
            )
        )
    program.days.append(day)
    db.add(program)
    await db.commit()
    return {"program_day_id": str(day.id)}


# ── Måltidsfoto: identifiera livsmedel + näringsdata ─────────


class _LLMFoodItem(BaseModel):
    name: str = Field(max_length=120)
    grams: float = Field(gt=0, le=3000)
    kcal_per_100g: float = Field(ge=0, le=900)
    protein_g_per_100g: float = Field(ge=0, le=100)
    carbs_g_per_100g: float = Field(ge=0, le=100)
    fat_g_per_100g: float = Field(ge=0, le=100)


class _LLMMeal(BaseModel):
    items: list[_LLMFoodItem] = Field(min_length=1, max_length=15)


@router.post("/meal-vision")
async def meal_vision(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    """Fota måltiden → identifierade livsmedel med uppskattad mängd och
    näringsvärden. Uppskattningar — användaren justerar innan loggning."""
    if (file.content_type or "") not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Skicka ett foto (JPEG/PNG/WebP).")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Bilden är för stor (max 10 MB).")

    prompt = (
        "Du är en noggrann nutritionist. Titta på fotot av måltiden. "
        "Identifiera varje enskilt livsmedel/komponent på tallriken, "
        "uppskatta mängden i gram (tänk på tallrikens storlek som referens) "
        "och ange typiska näringsvärden per 100 gram. Svenska namn. "
        "Svara med strikt JSON, inget annat:\n"
        '{"items": [{"name": "Grillad kycklingfilé", "grams": 150, '
        '"kcal_per_100g": 110, "protein_g_per_100g": 23, '
        '"carbs_g_per_100g": 0, "fat_g_per_100g": 2}]}'
    )
    try:
        raw = await ollama.chat(
            prompt,
            images_b64=[base64.b64encode(content).decode()],
            json_format=True,
        )
        meal = _LLMMeal.model_validate(json.loads(raw))
    except AIUnavailable as exc:
        raise HTTPException(
            503,
            "AI-tjänsten är inte igång. Starta Ollama: "
            "docker compose --profile ai up -d ollama",
        ) from exc
    except (json.JSONDecodeError, ValidationError) as exc:
        logger.warning("Ogiltigt måltidssvar från AI: %s", exc)
        raise HTTPException(502, "AI:n kunde inte tolka fotot — försök igen.")

    items = [
        {
            "name": item.name[:120],
            "grams": round(item.grams),
            "per_100g": {
                "kcal": round(item.kcal_per_100g, 1),
                "protein_g": round(item.protein_g_per_100g, 1),
                "carbs_g": round(item.carbs_g_per_100g, 1),
                "fat_g": round(item.fat_g_per_100g, 1),
            },
        }
        for item in meal.items
    ]
    return {"items": items}


# ── Gym-vision ────────────────────────────────────────────────


@router.post("/gym-vision")
async def gym_vision(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    if (file.content_type or "") not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "Skicka ett foto (JPEG/PNG/WebP).")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "Bilden är för stor (max 10 MB).")

    prompt = (
        "Titta på fotot från ett gym. Vilka av följande utrustningstyper "
        f"syns? {', '.join(EQUIPMENT_VOCAB)}. "
        'Svara med strikt JSON: {"equipment": ["..."]} — använd endast '
        "orden i listan."
    )
    try:
        raw = await ollama.chat(
            prompt,
            images_b64=[base64.b64encode(content).decode()],
            json_format=True,
        )
        detected = json.loads(raw).get("equipment", [])
    except AIUnavailable as exc:
        raise HTTPException(
            503,
            "AI-tjänsten är inte igång. Starta Ollama: "
            "docker compose --profile ai up -d ollama",
        ) from exc
    except (json.JSONDecodeError, AttributeError):
        raise HTTPException(502, "AI:n gav ett oanvändbart svar — försök igen.")

    equipment = [e for e in detected if isinstance(e, str) and e in EQUIPMENT_VOCAB]

    suggestions = []
    if equipment:
        exercises = await db.scalars(
            select(Exercise)
            .where(
                or_(Exercise.is_global.is_(True), Exercise.created_by == user.id)
            )
            .order_by(Exercise.name)
        )
        for exercise in exercises:
            if any(eq in exercise.equipment for eq in equipment):
                suggestions.append(
                    {
                        "id": str(exercise.id),
                        "name": exercise.name,
                        "muscle_groups": exercise.muscle_groups,
                        "equipment": exercise.equipment,
                    }
                )

    return {"equipment": equipment, "exercises": suggestions[:30]}
