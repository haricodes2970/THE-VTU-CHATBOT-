"""
scripts/reset_db.py
Drops and recreates all database tables. DEV ONLY — requires confirmation.
Run: python scripts/reset_db.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.core.config import settings
from loguru import logger


def reset():
    if settings.is_production:
        logger.error("ABORT: reset_db.py must not run in production!")
        sys.exit(1)

    confirm = input(
        "⚠️  This will DROP all tables and recreate them. Type 'yes' to confirm: "
    )
    if confirm.strip().lower() != "yes":
        logger.info("Aborted.")
        sys.exit(0)

    from backend.core.database import engine, Base
    from backend.models.models import (  # noqa: F401
        User, Circular, ExamSchedule, Subscription, Notification
    )

    logger.info("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Recreating all tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database reset complete!")


if __name__ == "__main__":
    reset()
