"""
backend/services/circular_service.py
Business logic for saving, retrieving, and searching circulars in PostgreSQL.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from loguru import logger

from backend.models.models import Circular


class CircularService:
    """Service layer for Circular model operations."""

    def save_circular(self, db: Session, circular_data: dict) -> Circular:
        """
        Save a circular to the database.
        Skips if the URL already exists (idempotent).
        """
        existing = db.execute(
            select(Circular).where(Circular.url == circular_data["url"])
        ).scalar_one_or_none()

        if existing:
            # If existing content is poor (short/empty), update with richer content
            new_content = circular_data.get("content") or ""
            if new_content and len(new_content) > len(existing.content or ""):
                existing.content = new_content
                existing.title = circular_data.get("title", existing.title)[:500]
                existing.is_indexed = False  # needs re-embedding with new content
                db.commit()
                logger.info(f"Updated content for circular: {existing.url[:80]}")
            else:
                logger.debug(f"Circular already exists: {circular_data['url']}")
            return existing

        circular = Circular(
            title=circular_data.get("title", "")[:500],
            url=circular_data["url"],
            pdf_path=circular_data.get("pdf_path"),
            content=circular_data.get("content"),
            circular_date=circular_data.get("circular_date") or circular_data.get("date"),
            scraped_at=datetime.utcnow(),
            # Timetable-specific fields
            scheme=circular_data.get("scheme"),
            course_type=circular_data.get("course_type"),
            exam_session=circular_data.get("exam_session"),
            semester_range=circular_data.get("semester_range"),
            pdf_hash=circular_data.get("pdf_hash"),
            is_superseded=circular_data.get("is_superseded", False),
            source_post_url=circular_data.get("source_post_url"),
        )
        db.add(circular)
        db.commit()
        db.refresh(circular)
        logger.info(f"Saved circular: {circular.title[:60]}")
        return circular

    def get_all_circulars(
        self, db: Session, page: int = 1, limit: int = 10
    ) -> tuple[list[Circular], int]:
        """Return paginated list of circulars and total count."""
        offset = (page - 1) * limit
        stmt = (
            select(Circular)
            .order_by(Circular.scraped_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = db.execute(stmt).scalars().all()
        total = db.execute(select(Circular)).scalars().all()
        return list(rows), len(total)

    def get_circular_by_id(self, db: Session, circular_id: int) -> Optional[Circular]:
        """Fetch a single circular by primary key."""
        return db.execute(
            select(Circular).where(Circular.id == circular_id)
        ).scalar_one_or_none()

    def search_circulars(
        self, db: Session, query: str, page: int = 1, limit: int = 10
    ) -> list[Circular]:
        """Full-text search on title and content."""
        offset = (page - 1) * limit
        pattern = f"%{query}%"
        stmt = (
            select(Circular)
            .where(
                or_(
                    Circular.title.ilike(pattern),
                    Circular.content.ilike(pattern),
                )
            )
            .order_by(Circular.scraped_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(db.execute(stmt).scalars().all())

    def mark_as_processed(self, db: Session, circular_id: int) -> None:
        """Mark a circular as text-processed (content extracted)."""
        circular = self.get_circular_by_id(db, circular_id)
        if circular:
            circular.is_processed = True
            db.commit()

    def get_unprocessed(self, db: Session) -> list[Circular]:
        """Return circulars that haven't been embedded into the vector DB yet."""
        stmt = select(Circular).where(
            Circular.is_indexed == False  # noqa: E712
        )
        return list(db.execute(stmt).scalars().all())

    def get_latest_timetable_pdf_url(
        self, db: Session, scheme: str | None = None, course_type: str | None = None
    ) -> str | None:
        """
        Return PDF URL of the most recently published non-superseded circular
        matching scheme + course_type. Used as last-resort fallback in the bot.
        """
        stmt = select(Circular).where(Circular.is_superseded == False)  # noqa: E712
        if scheme:
            stmt = stmt.where(Circular.scheme == scheme)
        if course_type:
            stmt = stmt.where(Circular.course_type == course_type)
        stmt = stmt.order_by(Circular.circular_date.desc()).limit(1)
        result = db.execute(stmt).scalar_one_or_none()
        return result.url if result else None

    def get_active_timetables_count(self, db: Session) -> int:
        """Count non-superseded, indexed timetables."""
        from sqlalchemy import func
        return db.execute(
            select(func.count(Circular.id)).where(
                Circular.is_superseded == False,  # noqa: E712
                Circular.is_indexed == True,  # noqa: E712
            )
        ).scalar() or 0

    def get_superseded_count(self, db: Session) -> int:
        """Count superseded circulars."""
        from sqlalchemy import func
        return db.execute(
            select(func.count(Circular.id)).where(Circular.is_superseded == True)  # noqa: E712
        ).scalar() or 0
