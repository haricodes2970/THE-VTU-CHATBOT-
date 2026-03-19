"""
backend/core/database.py
SQLAlchemy async engine setup and session factory.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from typing import Generator
from loguru import logger

from backend.core.config import settings


# ── Engine ───────────────────────────────────────────────────
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,       # detect stale connections
    pool_size=10,
    max_overflow=20,
    echo=settings.is_development,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Dependency ───────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency — yields a database session per request
    and guarantees cleanup even on exception.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_connection() -> bool:
    """Verify database is reachable (used in startup health check)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection OK")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False
