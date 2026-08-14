import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    units: Mapped[str] = mapped_column(String(10), default="metric")
    locale: Mapped[str] = mapped_column(String(10), default="sv-SE")
    # Profil: foto + ort och favoritträningsfrågor
    # {"city": ..., "fav_workout": ..., "fav_exercise": ..., "goal": ...}
    avatar_path: Mapped[str | None] = mapped_column(String(300))
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    # Shapiqo-ligan: Elo-rating som justeras när utmaningar avgörs
    elo_rating: Mapped[int] = mapped_column(Integer, default=1000)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
