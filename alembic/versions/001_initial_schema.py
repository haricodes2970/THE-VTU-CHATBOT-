"""Initial schema — users, circulars, exam_schedules, subscriptions, notifications

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("telegram_chat_id", sa.String(100), nullable=True),
        sa.Column("semester", sa.Integer(), nullable=True),
        sa.Column("branch", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── circulars ──────────────────────────────────────────────────
    op.create_table(
        "circulars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("pdf_path", sa.String(500), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("circular_date", sa.DateTime(), nullable=True),
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_indexed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("ix_circulars_id", "circulars", ["id"])
    op.create_index("ix_circulars_scraped_at", "circulars", ["scraped_at"])
    op.create_index("ix_circulars_pipeline", "circulars", ["is_indexed", "is_processed"])

    # ── exam_schedules ─────────────────────────────────────────────
    op.create_table(
        "exam_schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("circular_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("subject_code", sa.String(50), nullable=True),
        sa.Column("semester", sa.Integer(), nullable=True),
        sa.Column("exam_date", sa.DateTime(), nullable=True),
        sa.Column("exam_time", sa.String(50), nullable=True),
        sa.Column("branch", sa.String(100), nullable=True),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["circular_id"], ["circulars.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exam_schedules_id", "exam_schedules", ["id"])
    op.create_index("ix_exam_schedules_subject", "exam_schedules", ["subject"])
    op.create_index("ix_exam_schedules_semester", "exam_schedules", ["semester"])
    op.create_index("ix_exam_schedules_sem_sub", "exam_schedules", ["semester", "subject"])
    op.create_index("ix_exam_schedules_exam_date", "exam_schedules", ["exam_date"])

    # ── notification channel/status enums ──────────────────────────
    notification_channel = sa.Enum("email", "telegram", "firebase", name="notificationchannel")
    notification_status = sa.Enum("pending", "sent", "failed", name="notificationstatus")
    notification_channel.create(op.get_bind())
    notification_status.create(op.get_bind())

    # ── subscriptions ──────────────────────────────────────────────
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.Enum("email", "telegram", "firebase", name="notificationchannel"), nullable=False),
        sa.Column("notify_new_circular", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_exam_update", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("notify_results", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_subscriptions_id", "subscriptions", ["id"])

    # ── notifications ──────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("channel", sa.Enum("email", "telegram", "firebase", name="notificationchannel"), nullable=False),
        sa.Column("status", sa.Enum("pending", "sent", "failed", name="notificationstatus"), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"])
    op.create_index("ix_notifications_user_status", "notifications", ["user_id", "status"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("subscriptions")
    op.drop_table("exam_schedules")
    op.drop_table("circulars")
    op.drop_table("users")
    # Drop enums
    sa.Enum(name="notificationstatus").drop(op.get_bind())
    sa.Enum(name="notificationchannel").drop(op.get_bind())
