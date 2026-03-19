"""
backend/core/database_utils.py
Database utility functions: pagination, get_or_create, bulk_insert, transaction context.
"""
from contextlib import contextmanager
from typing import Any, Generator, Type, TypeVar

from sqlalchemy.orm import Session
from sqlalchemy import select
from loguru import logger

T = TypeVar("T")


def paginate(stmt, page: int, limit: int):
    """Apply OFFSET and LIMIT to a SQLAlchemy select statement."""
    offset = (page - 1) * limit
    return stmt.offset(offset).limit(limit)


def get_or_create(db: Session, model: Type[T], **kwargs) -> tuple[T, bool]:
    """
    Get an existing record or create a new one.
    Returns (instance, created: bool).
    """
    instance = db.execute(
        select(model).filter_by(**kwargs)
    ).scalar_one_or_none()

    if instance:
        return instance, False

    instance = model(**kwargs)
    db.add(instance)
    db.commit()
    db.refresh(instance)
    logger.debug(f"Created {model.__name__}: {kwargs}")
    return instance, True


def bulk_insert(db: Session, model: Type[T], data: list[dict]) -> int:
    """
    Efficiently bulk-insert a list of dicts as model instances.
    Returns the number of rows inserted.
    """
    if not data:
        return 0
    objects = [model(**row) for row in data]
    db.bulk_save_objects(objects)
    db.commit()
    logger.info(f"Bulk inserted {len(objects)} {model.__name__} rows")
    return len(objects)


@contextmanager
def transaction(db: Session) -> Generator[Session, None, None]:
    """
    Context manager that wraps operations in a try/commit/rollback block.
    Usage:
        with transaction(db) as session:
            session.add(obj)
    """
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction rolled back: {e}")
        raise
