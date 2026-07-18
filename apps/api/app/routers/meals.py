import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.models import FoodItem, MealEntry, MealTemplate, NutritionTarget, User
from app.nutrition_rdi import NUTRIENTS
from app.schemas_nutrition import (
    DayLog,
    DaySummary,
    FoodItemOut,
    MacroTotals,
    MealEntryCreate,
    MealEntryOut,
    MealTemplateCreate,
    MealTemplateOut,
    MicroOut,
    NutritionTargetOut,
    NutritionTargetUpdate,
    PhotoLog,
    TemplateApply,
    TemplateFromMeal,
)

router = APIRouter(prefix="/api/meals", tags=["meals"])
templates_router = APIRouter(prefix="/api/meal-templates", tags=["meals"])
targets_router = APIRouter(prefix="/api/nutrition-targets", tags=["meals"])


def _macros_for(food: FoodItem, grams: float) -> dict[str, float]:
    factor = grams / 100.0
    per = food.per_100g or {}
    return {
        key: round(float(per.get(key, 0) or 0) * factor, 1)
        for key in ("kcal", "protein_g", "carbs_g", "fat_g")
    }


async def _get_targets(user: User, db: AsyncSession) -> NutritionTarget:
    target = await db.scalar(
        select(NutritionTarget).where(NutritionTarget.user_id == user.id)
    )
    if target is None:
        target = NutritionTarget(user_id=user.id)
        db.add(target)
        await db.commit()
        await db.refresh(target)
    return target


async def _visible_food(
    food_item_id: uuid.UUID, user: User, db: AsyncSession
) -> FoodItem:
    food = await db.get(FoodItem, food_item_id)
    if food is None or (
        food.source not in ("off", "base") and food.created_by != user.id
    ):
        raise HTTPException(404, "Livsmedlet finns inte.")
    return food


async def _create_entry(
    user: User,
    db: AsyncSession,
    eaten_on: date,
    meal: str,
    food: FoodItem,
    grams: float,
) -> MealEntry:
    entry = MealEntry(
        user_id=user.id,
        eaten_on=eaten_on,
        meal=meal,
        food_item_id=food.id,
        grams=grams,
        **_macros_for(food, grams),
    )
    db.add(entry)
    return entry


@router.get("", response_model=DayLog)
async def day_log(
    day: date | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> DayLog:
    day = day or date.today()
    entries = list(
        await db.scalars(
            select(MealEntry)
            .where(MealEntry.user_id == user.id, MealEntry.eaten_on == day)
            .order_by(MealEntry.created_at)
        )
    )
    totals = MacroTotals(
        kcal=round(sum(float(e.kcal) for e in entries), 1),
        protein_g=round(sum(float(e.protein_g) for e in entries), 1),
        carbs_g=round(sum(float(e.carbs_g) for e in entries), 1),
        fat_g=round(sum(float(e.fat_g) for e in entries), 1),
    )

    # Mikronäringsämnen + % av RDI — beräknas ur livsmedlens källdata.
    # Bara ämnen där minst ett loggat livsmedel HAR data tas med, så att
    # saknad data aldrig ser ut som ett uppmätt nollintag.
    micro_totals: dict[str, float] = {}
    for entry in entries:
        per = entry.food_item.per_100g or {}
        factor = float(entry.grams) / 100.0
        for nutrient in NUTRIENTS:
            value = per.get(nutrient["key"])
            if value is None:
                continue
            micro_totals[nutrient["key"]] = micro_totals.get(
                nutrient["key"], 0.0
            ) + float(value) * factor
    micros = [
        MicroOut(
            key=n["key"],
            label=n["label"],
            unit=n["unit"],
            amount=round(micro_totals[n["key"]], 1),
            rdi=n["rdi"],
            percent=round(micro_totals[n["key"]] / n["rdi"] * 100),
            kind=n["kind"],
        )
        for n in NUTRIENTS
        if n["key"] in micro_totals
    ]

    targets = await _get_targets(user, db)
    return DayLog(
        day=day,
        entries=[MealEntryOut.model_validate(e) for e in entries],
        totals=totals,
        targets=NutritionTargetOut.model_validate(targets),
        micros=micros,
    )


@router.get("/summary", response_model=list[DaySummary])
async def summary(
    days: int = 7,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[DaySummary]:
    days = min(max(days, 1), 400)
    since = date.today() - timedelta(days=days - 1)
    rows = await db.execute(
        select(
            MealEntry.eaten_on,
            func.sum(MealEntry.kcal),
            func.sum(MealEntry.protein_g),
            func.sum(MealEntry.carbs_g),
            func.sum(MealEntry.fat_g),
            func.count(MealEntry.id),
        )
        .where(MealEntry.user_id == user.id, MealEntry.eaten_on >= since)
        .group_by(MealEntry.eaten_on)
        .order_by(MealEntry.eaten_on)
    )
    return [
        DaySummary(
            day=row[0],
            kcal=float(row[1]),
            protein_g=float(row[2]),
            carbs_g=float(row[3]),
            fat_g=float(row[4]),
            entry_count=row[5],
        )
        for row in rows
    ]


@router.post("", response_model=MealEntryOut, status_code=201)
async def add_entry(
    payload: MealEntryCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MealEntry:
    food = await _visible_food(payload.food_item_id, user, db)
    entry = await _create_entry(
        user, db, payload.eaten_on, payload.meal, food, payload.grams
    )
    await db.commit()
    entry = await db.scalar(
        select(MealEntry)
        .where(MealEntry.id == entry.id)
        .execution_options(populate_existing=True)
    )
    return entry


@router.post("/photo-log", response_model=list[MealEntryOut])
async def photo_log(
    payload: PhotoLog,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[MealEntry]:
    """Logga en AI-analyserad (och användarjusterad) måltid från foto.

    Varje identifierat livsmedel blir ett eget livsmedel i användarens
    bibliotek (återanvänds vid samma namn), så det även går att söka
    fram och logga manuellt nästa gång."""
    entries = []
    ratios = []
    for item in payload.items:
        name = item.name.strip()[:120]
        food = await db.scalar(
            select(FoodItem).where(
                FoodItem.created_by == user.id,
                FoodItem.source == "custom",
                FoodItem.name == name,
            )
        )
        if food is None:
            food = FoodItem(
                name=name,
                source="custom",
                per_100g=item.per_100g.model_dump(),
                created_by=user.id,
            )
            db.add(food)
            await db.flush()
        entries.append(
            await _create_entry(
                user, db, payload.eaten_on, payload.meal, food, item.grams
            )
        )
        # Kalibreringsunderlag: hur mycket justerade användaren AI:ns gissning?
        if item.ai_grams:
            ratio = float(item.grams) / float(item.ai_grams)
            if 0.3 <= ratio <= 3.0:  # orimliga kvoter förgiftar inte medianen
                ratios.append(round(ratio, 3))
    if ratios:
        profile = dict(user.profile or {})
        history = list(profile.get("portion_ratios") or [])
        history.extend(ratios)
        profile["portion_ratios"] = history[-30:]  # rullande fönster
        user.profile = profile
        db.add(user)
    await db.commit()
    ids = [e.id for e in entries]
    return list(
        await db.scalars(
            select(MealEntry)
            .where(MealEntry.id.in_(ids))
            .execution_options(populate_existing=True)
        )
    )


@router.delete("/{entry_id}", status_code=204)
async def delete_entry(
    entry_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    entry = await db.get(MealEntry, entry_id)
    if entry is None or entry.user_id != user.id:
        raise HTTPException(404, "Posten finns inte.")
    await db.delete(entry)
    await db.commit()


# ── Mallar ────────────────────────────────────────────────────


async def _template_out(
    template: MealTemplate, user: User, db: AsyncSession
) -> MealTemplateOut:
    food_ids = [uuid.UUID(item["food_item_id"]) for item in template.items]
    foods = list(
        await db.scalars(select(FoodItem).where(FoodItem.id.in_(food_ids)))
    ) if food_ids else []
    return MealTemplateOut(
        id=template.id,
        name=template.name,
        items=template.items,
        foods=[FoodItemOut.model_validate(f) for f in foods],
    )


@templates_router.get("", response_model=list[MealTemplateOut])
async def list_templates(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[MealTemplateOut]:
    templates = await db.scalars(
        select(MealTemplate)
        .where(MealTemplate.user_id == user.id)
        .order_by(MealTemplate.name)
    )
    return [await _template_out(t, user, db) for t in templates]


@templates_router.post("", response_model=MealTemplateOut, status_code=201)
async def create_template(
    payload: MealTemplateCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MealTemplateOut:
    for item in payload.items:
        await _visible_food(item.food_item_id, user, db)
    template = MealTemplate(
        user_id=user.id,
        name=payload.name,
        items=[
            {"food_item_id": str(i.food_item_id), "grams": i.grams}
            for i in payload.items
        ],
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return await _template_out(template, user, db)


@templates_router.post("/from-meal", response_model=MealTemplateOut, status_code=201)
async def create_template_from_meal(
    payload: TemplateFromMeal,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> MealTemplateOut:
    entries = list(
        await db.scalars(
            select(MealEntry).where(
                MealEntry.user_id == user.id,
                MealEntry.eaten_on == payload.eaten_on,
                MealEntry.meal == payload.meal,
            )
        )
    )
    if not entries:
        raise HTTPException(400, "Måltiden är tom — inget att spara som mall.")
    template = MealTemplate(
        user_id=user.id,
        name=payload.name,
        items=[
            {"food_item_id": str(e.food_item_id), "grams": float(e.grams)}
            for e in entries
        ],
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)
    return await _template_out(template, user, db)


@templates_router.post("/{template_id}/apply", response_model=list[MealEntryOut])
async def apply_template(
    template_id: uuid.UUID,
    payload: TemplateApply,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[MealEntry]:
    template = await db.get(MealTemplate, template_id)
    if template is None or template.user_id != user.id:
        raise HTTPException(404, "Mallen finns inte.")

    entries = []
    for item in template.items:
        food = await _visible_food(uuid.UUID(item["food_item_id"]), user, db)
        entries.append(
            await _create_entry(
                user, db, payload.eaten_on, payload.meal, food, item["grams"]
            )
        )
    await db.commit()
    ids = [e.id for e in entries]
    return list(
        await db.scalars(
            select(MealEntry)
            .where(MealEntry.id.in_(ids))
            .execution_options(populate_existing=True)
        )
    )


@templates_router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    template = await db.get(MealTemplate, template_id)
    if template is None or template.user_id != user.id:
        raise HTTPException(404, "Mallen finns inte.")
    await db.delete(template)
    await db.commit()


# ── Mål ───────────────────────────────────────────────────────


@targets_router.get("", response_model=NutritionTargetOut)
async def get_targets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> NutritionTarget:
    return await _get_targets(user, db)


@targets_router.put("", response_model=NutritionTargetOut)
async def update_targets(
    payload: NutritionTargetUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> NutritionTarget:
    target = await _get_targets(user, db)
    target.kcal = payload.kcal
    target.protein_g = payload.protein_g
    target.carbs_g = payload.carbs_g
    target.fat_g = payload.fat_g
    await db.commit()
    await db.refresh(target)
    return target
