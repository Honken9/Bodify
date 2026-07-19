import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Friendship(Base):
    """Vänskap: user_id skickade förfrågan, friend_id accepterar."""

    __tablename__ = "friendships"
    __table_args__ = (UniqueConstraint("user_id", "friend_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    friend_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(10), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


CHALLENGE_METRICS = {
    "workout_count",  # flest pass (styrka + kondition)
    "weight_loss_kg",  # störst viktnedgång i kg
    "fat_loss_percent",  # störst fettnedgång i procentenheter
    "distance_km",  # längst distans
    "steps_total",  # flest steg totalt (bästa källan per dag)
    "sleep_score_avg",  # högst sömnpoäng i snitt
    "sleep_hours_avg",  # mest sömn i snitt (h/natt)
    "active_days",  # flest dagar med minst ett pass
    "workout_minutes",  # flest träningsminuter (styrka + kondition)
    "logged_days",  # flest dagar med loggad kost
}


class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    creator_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    metric: Mapped[str] = mapped_column(String(30))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    # is_open: vem som helst kan gå med (veckoutmaningar m.m.)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    # standard = tävling, weekly = automatisk veckoutmaning,
    # habit = vana ("X pass/vecka" — alla som klarar kravet vinner)
    kind: Mapped[str] = mapped_column(String(20), default="standard")
    target: Mapped[dict | None] = mapped_column(JSON)  # habit: {"per_week": 3}
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    participants: Mapped[list["ChallengeParticipant"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan", lazy="selectin"
    )


class ChallengeParticipant(Base):
    __tablename__ = "challenge_participants"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Startvärden låses vid join (t.ex. {"weight": 84.0})
    baseline: Mapped[dict] = mapped_column(JSON, default=dict)

    challenge: Mapped[Challenge] = relationship(back_populates="participants")


class ChallengeInvite(Base):
    """Inbjudan till en utmaning — låter vem som helst i utmaningen bjuda
    in andra användare, som då kan gå med utan att vara vän med skaparen."""

    __tablename__ = "challenge_invites"
    __table_args__ = (UniqueConstraint("challenge_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    invited_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChallengeCheer(Base):
    """👏 på en händelse i utmaningens aktivitetsflöde."""

    __tablename__ = "challenge_cheers"
    __table_args__ = (
        UniqueConstraint("challenge_id", "item_kind", "item_id", "actor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), index=True
    )
    item_kind: Mapped[str] = mapped_column(String(10))  # strength|cardio
    item_id: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChallengeSnapshot(Base):
    """Nattligt jobb sparar dagens värde per deltagare — driver leaderboard-
    historik och 'vän gick om dig'-notiser."""

    __tablename__ = "challenge_snapshots"

    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("challenges.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(12, 3))
