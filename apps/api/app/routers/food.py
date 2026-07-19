import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.integrations import openfoodfacts
from app.models import FoodFavorite, FoodItem, MealEntry, User
from app.schemas_nutrition import FoodItemCreate, FoodItemOut, RecentFood

router = APIRouter(prefix="/api/food", tags=["food"])

# Delade källor som alla användare får se ("base" = inbyggda förslag)
SHARED_SOURCES = ("off", "base")


def _visible(user: User):
    return or_(
        FoodItem.source.in_(SHARED_SOURCES), FoodItem.created_by == user.id
    )


@router.get("/recent", response_model=list[RecentFood])
async def recent_foods(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[RecentFood]:
    """De 10 senast loggade livsmedlen (unika), med senaste gramvikten —
    snabbval för det man äter ofta."""
    entries = await db.scalars(
        select(MealEntry)
        .where(MealEntry.user_id == user.id)
        .order_by(MealEntry.created_at.desc())
        .limit(60)
    )
    recent: list[RecentFood] = []
    seen: set = set()
    for entry in entries:
        if entry.food_item_id in seen:
            continue
        seen.add(entry.food_item_id)
        recent.append(
            RecentFood(
                food=FoodItemOut.model_validate(entry.food_item),
                grams=float(entry.grams),
                last_eaten=entry.eaten_on,
            )
        )
        if len(recent) == 10:
            break
    return recent


@router.get("/favorites", response_model=list[FoodItemOut])
async def list_favorites(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[FoodItem]:
    favorites = await db.scalars(
        select(FoodFavorite)
        .where(FoodFavorite.user_id == user.id)
        .order_by(FoodFavorite.created_at.desc())
    )
    return [f.food_item for f in favorites]


@router.put("/favorites/{food_item_id}", status_code=204)
async def add_favorite(
    food_item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    food = await db.get(FoodItem, food_item_id)
    if food is None or (
        food.source not in SHARED_SOURCES and food.created_by != user.id
    ):
        raise HTTPException(404, "Livsmedlet finns inte.")
    existing = await db.get(FoodFavorite, (user.id, food_item_id))
    if existing is None:
        db.add(FoodFavorite(user_id=user.id, food_item_id=food_item_id))
        await db.commit()


@router.delete("/favorites/{food_item_id}", status_code=204)
async def remove_favorite(
    food_item_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> None:
    favorite = await db.get(FoodFavorite, (user.id, food_item_id))
    if favorite is not None:
        await db.delete(favorite)
        await db.commit()


@router.get("/suggestions", response_model=list[FoodItemOut])
async def list_suggestions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[FoodItem]:
    """Inbyggda basförslag — vanliga livsmedel med typvärden per 100 g."""
    rows = await db.scalars(
        select(FoodItem)
        .where(FoodItem.source == "base")
        .order_by(FoodItem.name)
    )
    return list(rows)


@router.get("/barcode/{barcode}", response_model=FoodItemOut)
async def lookup_barcode(
    barcode: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> FoodItem:
    # EAN/UPC är alltid 6–14 siffror — allt annat avvisas innan värdet
    # används i uppslag mot Open Food Facts.
    if not re.fullmatch(r"\d{6,14}", barcode):
        raise HTTPException(400, "Ogiltig streckkod.")
    cached = await db.scalar(select(FoodItem).where(FoodItem.barcode == barcode))
    if cached is not None:
        return cached

    try:
        product = await openfoodfacts.fetch_product(barcode)
    except openfoodfacts.OFFUnavailable:
        raise HTTPException(
            502,
            "Livsmedelsdatabasen (Open Food Facts) svarar inte just nu — "
            "prova igen om en stund.",
        )
    if product is None:
        raise HTTPException(
            404, "Produkten finns inte i Open Food Facts — lägg in den manuellt."
        )

    item = FoodItem(
        barcode=product["barcode"] or barcode,
        name=product["name"],
        brand=product["brand"],
        source="off",
        per_100g=product["per_100g"],
        serving_g=product.get("serving_g"),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/search", response_model=list[FoodItemOut])
async def search_food(
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> list[FoodItem]:
    q = q.strip()
    if len(q) < 2:
        return []

    local = list(
        await db.scalars(
            select(FoodItem)
            .where(_visible(user), FoodItem.name.ilike(f"%{q}%"))
            .order_by(FoodItem.name)
            .limit(25)
        )
    )

    # Komplettera med OFF-sökning; träffar cachas så de får ett id
    # som måltidsloggen kan referera till.
    if len(local) < 10:
        remote = await openfoodfacts.search_products(q, limit=10)
        known_barcodes = {
            f.barcode for f in local if f.barcode is not None
        } | set(
            await db.scalars(
                select(FoodItem.barcode).where(
                    FoodItem.barcode.in_(
                        [p["barcode"] for p in remote if p["barcode"]]
                    )
                )
            )
        )
        for product in remote:
            if not product["barcode"] or product["barcode"] in known_barcodes:
                continue
            item = FoodItem(
                barcode=product["barcode"],
                name=product["name"],
                brand=product["brand"],
                source="off",
                per_100g=product["per_100g"],
                serving_g=product.get("serving_g"),
            )
            db.add(item)
            local.append(item)
            known_barcodes.add(product["barcode"])
        await db.commit()

    return local


class ServingUpdate(BaseModel):
    grams: float = Field(gt=0, le=2000)


@router.patch("/{food_item_id}/serving", response_model=FoodItemOut)
async def set_serving(
    food_item_id: uuid.UUID,
    payload: ServingUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> FoodItem:
    """Lär appen vad ett styck väger ("1 kex = 12 g") — därefter kan
    varan loggas i antal istället för gram."""
    food = await db.get(FoodItem, food_item_id)
    if food is None or (
        food.source not in SHARED_SOURCES and food.created_by != user.id
    ):
        raise HTTPException(404, "Livsmedlet finns inte.")
    food.serving_g = payload.grams
    await db.commit()
    await db.refresh(food)
    return food


@router.post("", response_model=FoodItemOut, status_code=201)
async def create_food(
    payload: FoodItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> FoodItem:
    barcode = payload.barcode
    if barcode:
        # Streckkoden är unik — finns varan redan återanvänds den
        existing = await db.scalar(
            select(FoodItem).where(FoodItem.barcode == barcode)
        )
        if existing is not None:
            if existing.source in SHARED_SOURCES or existing.created_by == user.id:
                return existing
            barcode = None  # koden ägs av någon annans privata post
    item = FoodItem(
        barcode=barcode,
        name=payload.name,
        brand=payload.brand,
        source="custom",
        per_100g=payload.per_100g.model_dump(),
        created_by=user.id,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item
