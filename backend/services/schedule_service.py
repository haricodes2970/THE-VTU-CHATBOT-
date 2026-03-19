"""
backend/services/schedule_service.py
Business logic for exam schedule queries and persistence.
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from backend.models.models import ExamSchedule


class ScheduleService:
    """Service layer for ExamSchedule model operations."""

    def get_schedule(
        self,
        db: Session,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> list[ExamSchedule]:
        """Return exam schedules filtered by optional semester, branch, subject."""
        stmt = select(ExamSchedule).order_by(ExamSchedule.exam_date.asc())
        if semester is not None:
            stmt = stmt.where(ExamSchedule.semester == semester)
        if branch:
            stmt = stmt.where(ExamSchedule.branch.ilike(f"%{branch}%"))
        if subject:
            stmt = stmt.where(ExamSchedule.subject.ilike(f"%{subject}%"))
        return list(db.execute(stmt).scalars().all())

    def get_upcoming_exams(self, db: Session, days: int = 7) -> list[ExamSchedule]:
        """Return exams scheduled within the next `days` days."""
        now = datetime.utcnow()
        deadline = now + timedelta(days=days)
        stmt = (
            select(ExamSchedule)
            .where(ExamSchedule.exam_date >= now)
            .where(ExamSchedule.exam_date <= deadline)
            .order_by(ExamSchedule.exam_date.asc())
        )
        return list(db.execute(stmt).scalars().all())

    def save_exam_schedule(self, db: Session, schedule_data: list[dict]) -> int:
        """Bulk insert exam schedule rows. Returns count inserted."""
        inserted = 0
        for row in schedule_data:
            try:
                obj = ExamSchedule(
                    subject=row.get("subject", "")[:255],
                    subject_code=row.get("subject_code"),
                    semester=row.get("semester"),
                    exam_date=row.get("exam_date"),
                    exam_time=row.get("exam_time"),
                    branch=row.get("branch"),
                    academic_year=row.get("academic_year"),
                    circular_id=row.get("circular_id"),
                )
                db.add(obj)
                inserted += 1
            except Exception as e:
                logger.error(f"Error inserting exam schedule row: {e}")
        db.commit()
        logger.info(f"Inserted {inserted} exam schedule rows")
        return inserted

    def get_by_subject(self, db: Session, subject_name: str) -> list[ExamSchedule]:
        """Find exam schedule rows matching a subject name (partial, case-insensitive)."""
        stmt = (
            select(ExamSchedule)
            .where(ExamSchedule.subject.ilike(f"%{subject_name}%"))
            .order_by(ExamSchedule.exam_date.asc())
        )
        return list(db.execute(stmt).scalars().all())
