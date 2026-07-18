import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileUpdate(BaseModel):
    """Profilfrågorna — ort + tre favoritträningsfrågor. Alla frivilliga."""

    city: str | None = Field(default=None, max_length=120)
    fav_workout: str | None = Field(default=None, max_length=120)
    fav_exercise: str | None = Field(default=None, max_length=120)
    goal: str | None = Field(default=None, max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    is_admin: bool
    units: str
    locale: str
    profile: dict = {}
    avatar_url: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    units: str | None = Field(default=None, pattern="^(metric|imperial)$")
    locale: str | None = Field(default=None, max_length=10)
    profile: ProfileUpdate | None = None
