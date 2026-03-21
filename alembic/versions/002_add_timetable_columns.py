"""Add timetable dedup and revision tracking columns to circulars

Revision ID: 002
Revises: 001
Create Date: 2026-03-21 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("circulars", sa.Column("scheme", sa.String(20), nullable=True))
    op.add_column("circulars", sa.Column("course_type", sa.String(20), nullable=True))
    op.add_column("circulars", sa.Column("exam_session", sa.String(100), nullable=True))
    op.add_column("circulars", sa.Column("semester_range", sa.String(20), nullable=True))
    op.add_column("circulars", sa.Column("pdf_hash", sa.String(64), nullable=True))
    op.add_column(
        "circulars",
        sa.Column("is_superseded", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("circulars", sa.Column("source_post_url", sa.String(1000), nullable=True))
    op.add_column(
        "circulars",
        sa.Column(
            "superseded_by_id",
            sa.Integer(),
            sa.ForeignKey("circulars.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_circulars_dedup", "circulars", ["exam_session", "scheme", "semester_range"]
    )


def downgrade() -> None:
    op.drop_index("ix_circulars_dedup", table_name="circulars")
    op.drop_column("circulars", "superseded_by_id")
    op.drop_column("circulars", "source_post_url")
    op.drop_column("circulars", "is_superseded")
    op.drop_column("circulars", "pdf_hash")
    op.drop_column("circulars", "semester_range")
    op.drop_column("circulars", "exam_session")
    op.drop_column("circulars", "course_type")
    op.drop_column("circulars", "scheme")
