"""Progressfoton: fas-tagg (före/mittemellan/efter)

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Befintliga foton är rimligen tagna i början av resan → "before"
    op.add_column(
        "progress_photos",
        sa.Column("phase", sa.String(10), nullable=False, server_default="before"),
    )


def downgrade() -> None:
    op.drop_column("progress_photos", "phase")
