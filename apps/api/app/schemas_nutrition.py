import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field

MEALS = ("breakfast", "lunch", "dinner", "snack")


class Per100g(BaseModel):
    kcal: float = Field(ge=0, default=0)
    protein_g: float = Field(ge=0, default=0)
    carbs_g: float = Field(ge=0, default=0)
    fat_g: float = Field(ge=0, default=0)
    fiber_g: float = Field(ge=0, default=0)


class FoodItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    barcode: str | None
    name: str
    brand: str | None
    source: str
    per_100g: dict


class FoodItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    per_100g: Per100g


class RecentFood(BaseModel):
    """Snabbval: nyligen loggat livsmedel med senaste gramvikten."""

    food: FoodItemOut
    grams: float
    last_eaten: date


class MealEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    eaten_on: date
    meal: str
    food_item: FoodItemOut
    grams: float
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float


class MealEntryCreate(BaseModel):
    eaten_on: date
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    food_item_id: uuid.UUID
    grams: float = Field(gt=0, le=5000)


class MacroTotals(BaseModel):
    kcal: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0


class NutritionTargetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kcal: int
    protein_g: int
    carbs_g: int
    fat_g: int


class NutritionTargetUpdate(BaseModel):
    kcal: int = Field(ge=500, le=10000)
    protein_g: int = Field(ge=0, le=1000)
    carbs_g: int = Field(ge=0, le=2000)
    fat_g: int = Field(ge=0, le=500)


class MicroOut(BaseModel):
    """Ett näringsämne för dagen, med % av referensvärdet (RDI/maxgräns).

    Visas bara när minst ett loggat livsmedel har källdata för ämnet."""

    key: str
    label: str
    unit: str
    amount: float
    rdi: float
    percent: int
    kind: str  # rdi = nå upp till, max = håll dig under


class DayLog(BaseModel):
    day: date
    entries: list[MealEntryOut]
    totals: MacroTotals
    targets: NutritionTargetOut
    micros: list[MicroOut] = []


class DaySummary(BaseModel):
    day: date
    kcal: float
    protein_g: float
    carbs_g: float
    fat_g: float
    entry_count: int


class TemplateItem(BaseModel):
    food_item_id: uuid.UUID
    grams: float = Field(gt=0, le=5000)


class MealTemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    items: list[dict]
    foods: list[FoodItemOut] = []


class MealTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    items: list[TemplateItem] = Field(min_length=1)


class TemplateFromMeal(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    eaten_on: date
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")


class TemplateApply(BaseModel):
    eaten_on: date
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")


# ── Måltidsfoto (AI) ─────────────────────────────────────────


class PhotoFoodItem(BaseModel):
    """Ett identifierat livsmedel från ett måltidsfoto — justerbart av
    användaren innan loggning."""

    name: str = Field(min_length=1, max_length=120)
    grams: float = Field(gt=0, le=3000)
    # AI:ns ursprungliga gissning (före användarens justering) — används
    # för att kalibrera framtida portionsuppskattningar
    ai_grams: float | None = Field(default=None, gt=0, le=3000)
    per_100g: Per100g


class PhotoLog(BaseModel):
    eaten_on: date
    meal: str = Field(pattern="^(breakfast|lunch|dinner|snack)$")
    items: list[PhotoFoodItem] = Field(min_length=1, max_length=15)
