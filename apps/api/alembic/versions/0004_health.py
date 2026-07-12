"""Integrationer & hälsodata: OAuth, ingest-tokens, kroppsmetrik,
sömn, kondition, mål

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("access_token_enc", sa.String(1024), nullable=False),
        sa.Column("refresh_token_enc", sa.String(1024), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_user_id", sa.String(64), nullable=True, index=True),
        sa.Column("scopes", sa.String(256), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "provider"),
    )

    op.create_table(
        "ingest_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "label", sa.String(120), nullable=False, server_default="Apple Health"
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_ingest_tokens_token_hash", "ingest_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "body_metrics",
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("metric", sa.String(30), primary_key=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("source", sa.String(20), primary_key=True),
        sa.Column("value", sa.Numeric(10, 3), nullable=False),
        sa.Column("raw", sa.JSON(), nullable=True),
    )
    op.create_index(
        "ix_body_metrics_lookup",
        "body_metrics",
        ["user_id", "metric", "measured_at"],
    )

    op.create_table(
        "sleep_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deep_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rem_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("light_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("awake_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "source", sa.String(20), nullable=False, server_default="apple_health"
        ),
        sa.UniqueConstraint("user_id", "start_at", "source"),
    )

    op.create_table(
        "cardio_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("duration_s", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Numeric(10, 1), nullable=True),
        sa.Column("avg_hr", sa.Numeric(5, 1), nullable=True),
        sa.Column("max_hr", sa.Numeric(5, 1), nullable=True),
        sa.Column("avg_pace_s_per_km", sa.Numeric(7, 1), nullable=True),
        sa.Column("calories", sa.Numeric(7, 1), nullable=True),
        sa.Column("raw", sa.JSON(), nullable=True),
        sa.UniqueConstraint("user_id", "source", "external_id"),
    )

    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        # TimescaleDB-hypertabell för kroppsmetrik om tillägget finns
        # (partitionskolumnen measured_at ingår i primärnyckeln).
        op.execute(
            """
            DO $$ BEGIN
              IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                PERFORM create_hypertable(
                  'body_metrics', 'measured_at',
                  if_not_exists => TRUE, migrate_data => TRUE);
              END IF;
            END $$;
            """
        )
        uid = "current_setting('app.user_id', true)::uuid"
        for table in (
            "oauth_connections",
            "ingest_tokens",
            "body_metrics",
            "sleep_sessions",
            "cardio_activities",
            "goals",
        ):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant ON {table} USING (user_id = {uid})")


def downgrade() -> None:
    for table in (
        "goals",
        "cardio_activities",
        "sleep_sessions",
        "body_metrics",
        "ingest_tokens",
        "oauth_connections",
    ):
        op.drop_table(table)
