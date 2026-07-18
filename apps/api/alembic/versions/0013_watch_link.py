"""Klockpass ↔ styrkepass: länkning + position på loggade pass

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Klockinspelade gympass kopplas till Shapiqo-loggade styrkepass så
    # de inte dubbelräknas; opt-out gör att en isärkopplad länk inte
    # återskapas av nästa synk.
    # batch_alter_table: SQLite (demo/test) kan inte ALTER:a constraints —
    # på Postgres blir det vanliga ALTER TABLE-satser
    with op.batch_alter_table("cardio_activities") as batch:
        batch.add_column(sa.Column("linked_session_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column(
                "autolink_opt_out",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.create_foreign_key(
            "fk_cardio_linked_session",
            "workout_sessions",
            ["linked_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
    # Position när ett gympass loggas — så det kan visas på träningskartan
    op.add_column(
        "workout_sessions", sa.Column("start_lat", sa.Numeric(9, 6), nullable=True)
    )
    op.add_column(
        "workout_sessions", sa.Column("start_lng", sa.Numeric(9, 6), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("workout_sessions", "start_lng")
    op.drop_column("workout_sessions", "start_lat")
    with op.batch_alter_table("cardio_activities") as batch:
        batch.drop_constraint("fk_cardio_linked_session", type_="foreignkey")
        batch.drop_column("autolink_opt_out")
        batch.drop_column("linked_session_id")
