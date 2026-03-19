"""
backend/core/logger.py
Loguru logger configuration with file rotation and env-based log levels.
"""
import sys
from pathlib import Path
from loguru import logger

from backend.core.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logger() -> None:
    """Configure loguru for the application."""
    logger.remove()  # Remove default handler

    log_level = "DEBUG" if settings.is_development else "INFO"

    # Console handler
    logger.add(
        sys.stdout,
        level=log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # File handler with rotation
    logger.add(
        LOG_DIR / "app.log",
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
    )

    # Separate error log
    logger.add(
        LOG_DIR / "errors.log",
        level="ERROR",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} — {message}",
    )


# Apply config on import
setup_logger()
