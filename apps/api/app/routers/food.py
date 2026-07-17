import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db import get_session
from app.integrations import openfoodfacts
from app.models import FoodItem, User
from app.schemas_nutrition import FoodItemCreate, FoodItemOut

router = APIRouter(prefix="/api/food", tags=["food"])


def _visible(user: User):
    return or_(FoodItem.source == "off", FoodItem.created_by == user.id)


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

    product = await openfoodfacts.fetch_product(barcode)
    if product is None:
        raise HTTPException(
            404, "Produkten hittades inte — lägg gärna in den manuellt."
        )

    item = FoodItem(
        barcode=product["barcode"] or barcode,
        name=product["name"],
        brand=product["brand"],
        source="off",
        per_100g=product["per_100g"],
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
            )
            db.add(item)
            local.append(item)
            known_barcodes.add(product["barcode"])
        await db.commit()

    return local


@router.post("", response_model=FoodItemOut, status_code=201)
async def create_food(
    payload: FoodItemCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
) -> FoodItem:
    item = FoodItem(
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
