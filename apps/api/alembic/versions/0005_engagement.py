"""Progressfoton och push-prenumerationer

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-12

"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "progress_photos",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "taken_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("pose", sa.String(10), nullable=False, server_default="front"),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column(
            "content_type",
            sa.String(64),
            nullable=False,
            server_default="image/jpeg",
        ),
    )

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("endpoint", sa.String(1024), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(256), nullable=False),
        sa.Column("auth", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    if op.get_bind().dialect.name == "postgresql":
        uid = "current_setting('app.user_id', true)::uuid"
        for table in ("progress_photos", "push_subscriptions"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY tenant ON {table} USING (user_id = {uid})")


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_table("progress_photos")
