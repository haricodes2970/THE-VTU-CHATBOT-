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
            logger.debug(f"Circular already exists: {circular_data['url']}")
            return existing

        circular = Circular(
            title=circular_data.get("title", "")[:500],
            url=circular_data["url"],
            pdf_path=circular_data.get("pdf_path"),
            content=circular_data.get("content"),
            circular_date=circular_data.get("date"),
            scraped_at=datetime.utcnow(),
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
