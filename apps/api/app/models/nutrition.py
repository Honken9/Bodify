import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class FoodItem(Base):
    """Livsmedel — cache av Open Food Facts-uppslag samt egna livsmedel.

    `per_100g` innehåller näringsvärden per 100 g:
    {"kcal": ..., "protein_g": ..., "carbs_g": ..., "fat_g": ..., "fiber_g": ...}
    """

    __tablename__ = "food_items"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    barcode: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    brand: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(20), default="custom")  # off|custom
    per_100g: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL")
    )


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    eaten_on: Mapped[date] = mapped_column(Date, index=True)
    meal: Mapped[str] = mapped_column(String(20))  # breakfast|lunch|dinner|snack
    food_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("food_items.id", ondelete="CASCADE")
    )
    grams: Mapped[float] = mapped_column(Numeric(7, 1))
    # Makron denormaliserade vid loggning för snabba dagssummor/dashboards
    kcal: Mapped[float] = mapped_column(Numeric(8, 1), default=0)
    protein_g: Mapped[float] = mapped_column(Numeric(7, 1), default=0)
    carbs_g: Mapped[float] = mapped_column(Numeric(7, 1), default=0)
    fat_g: Mapped[float] = mapped_column(Numeric(7, 1), default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    food_item: Mapped[FoodItem] = relationship(lazy="selectin")


class MealTemplate(Base):
    """Måltidsmall, t.ex. "Min standardfrukost".

    `items` = [{"food_item_id": "...", "grams": 120}, ...]
    """

    __tablename__ = "meal_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    items: Mapped[list[dict]] = mapped_column(JSON, default=list)


class NutritionTarget(Base):
    __tablename__ = "nutrition_targets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    kcal: Mapped[int] = mapped_column(Integer, default=2500)
    protein_g: Mapped[int] = mapped_column(Integer, default=150)
    carbs_g: Mapped[int] = mapped_column(Integer, default=250)
    fat_g: Mapped[int] = mapped_column(Integer, default=80)
