"""
backend/services/user_service.py
Business logic for user creation and subscription management.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from backend.models.models import User, Subscription, NotificationChannel


class UserService:
    """Service layer for User and Subscription model operations."""

    def create_user(
        self,
        db: Session,
        email: str,
        name: str,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
    ) -> User:
        """Create a new user or return existing one if email already registered."""
        existing = db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()
        if existing:
            logger.debug(f"User already exists: {email}")
            return existing

        user = User(email=email, name=name, semester=semester, branch=branch)
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"Created user: {email}")
        return user

    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.execute(
            select(User).where(User.email == email)
        ).scalar_one_or_none()

    def get_user_by_id(self, db: Session, user_id: int) -> Optional[User]:
        return db.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

    def update_preferences(
        self,
        db: Session,
        user_id: int,
        semester: Optional[int] = None,
        branch: Optional[str] = None,
    ) -> Optional[User]:
        user = self.get_user_by_id(db, user_id)
        if not user:
            return None
        if semester is not None:
            user.semester = semester
        if branch is not None:
            user.branch = branch
        db.commit()
        db.refresh(user)
        return user

    def create_subscription(
        self, db: Session, user_id: int, channels: list[str]
    ) -> list[Subscription]:
        """Create subscription records for specified channels."""
        subs = []
        channel_map = {
            "email": NotificationChannel.EMAIL,
            "telegram": NotificationChannel.TELEGRAM,
        }
        for ch_str in channels:
            ch = channel_map.get(ch_str)
            if ch is None:
                continue
            # Check if subscription already exists
            existing = db.execute(
                select(Subscription).where(
                    Subscription.user_id == user_id,
                    Subscription.channel == ch,
                )
            ).scalar_one_or_none()
            if existing:
                subs.append(existing)
                continue
            sub = Subscription(user_id=user_id, channel=ch)
            db.add(sub)
            subs.append(sub)
        db.commit()
        return subs
