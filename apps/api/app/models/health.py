import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class OAuthConnection(Base):
    __tablename__ = "oauth_connections"
    __table_args__ = (UniqueConstraint("user_id", "provider"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20))  # strava|withings
    access_token_enc: Mapped[str] = mapped_column(String(1024))
    refresh_token_enc: Mapped[str] = mapped_column(String(1024))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scopes: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngestToken(Base):
    """Per-användar-token för Apple Health-ingest (Health Auto Export)."""

    __tablename__ = "ingest_tokens"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), default="Apple Health")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BodyMetric(Base):
    """Generisk tidsserie för kroppsdata & återhämtning.

    Ett nytt mätetal = ett nytt `metric`-värde — ingen migrering behövs.
    Naturlig nyckel (user, metric, tidpunkt, källa) gör inmatningen idempotent:
    samma mätning från samma källa skrivs bara en gång.
    """

    __tablename__ = "body_metrics"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    metric: Mapped[str] = mapped_column(String(30), primary_key=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(20), primary_key=True)
    value: Mapped[float] = mapped_column(Numeric(10, 3))
    raw: Mapped[dict | None] = mapped_column(JSON)


# Kända mätetal (valideras vid inmatning)
METRICS = {
    "weight",  # kg
    "fat_percent",  # %
    "muscle_mass",  # kg
    "hydration",  # kg
    "bone_mass",  # kg
    "pwv",  # m/s (pulsvågshastighet)
    "resting_hr",  # slag/min
    "hrv",  # ms (SDNN från Apple Health)
    "vo2max",  # ml/kg/min (konditionsnivå)
    "steps",  # antal/dag
    "diastolic_bp",  # mmHg
    "systolic_bp",  # mmHg
    "spo2",  # % syremättnad
    "sleep_duration",  # timmar sömn per natt
    "sleep_score",  # 0–100 (Withings sömnpoäng)
    "hr_avg",  # dagens snittpuls (slag/min)
    "hr_min",  # dagens lägsta puls
    "hr_max",  # dagens högsta puls
}


class SleepSession(Base):
    __tablename__ = "sleep_sessions"
    __table_args__ = (UniqueConstraint("user_id", "start_at", "source"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deep_s: Mapped[int] = mapped_column(Integer, default=0)
    rem_s: Mapped[int] = mapped_column(Integer, default=0)
    light_s: Mapped[int] = mapped_column(Integer, default=0)
    awake_s: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="apple_health")


class CardioActivity(Base):
    __tablename__ = "cardio_activities"
    __table_args__ = (UniqueConstraint("user_id", "source", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(20))  # run|ride|walk|swim|other
    source: Mapped[str] = mapped_column(String(20))  # strava|apple_health|manual
    external_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(String(200))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_s: Mapped[int] = mapped_column(Integer)
    distance_m: Mapped[float | None] = mapped_column(Numeric(10, 1))
    avg_hr: Mapped[float | None] = mapped_column(Numeric(5, 1))
    max_hr: Mapped[float | None] = mapped_column(Numeric(5, 1))
    avg_pace_s_per_km: Mapped[float | None] = mapped_column(Numeric(7, 1))
    calories: Mapped[float | None] = mapped_column(Numeric(7, 1))
    raw: Mapped[dict | None] = mapped_column(JSON)
    # Klockinspelat gympass som slagits ihop med ett loggat styrkepass —
    # länkade pass räknas inte som egna i statistik/listor
    linked_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("workout_sessions.id", ondelete="SET NULL")
    )
    autolink_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)


class Goal(Base):
    """Mål, t.ex. 10 km på 45 min eller ner till 11 % fett.

    target (JSON):
      pace_distance: {"distance_m": 10000, "time_s": 2700}
      body_metric:   {"metric": "fat_percent", "value": 11, "baseline": 18.2}
      frequency:     {"sessions_per_week": 4}
    """

    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    target: Mapped[dict] = mapped_column(JSON)
    deadline: Mapped[date | None] = mapped_column(Date)
    achieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
