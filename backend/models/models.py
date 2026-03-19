"""
backend/models/models.py
All database ORM models — Users, Circulars, ExamSchedules, Subscriptions, Notifications.
"""
from datetime import datetime
from sqlalchemy import (
    String, Text, Integer, Boolean, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from backend.core.database import Base


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    FIREBASE = "firebase"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


# ── Users ─────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship("Subscription", back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


# ── Circulars ─────────────────────────────────────────────────
class Circular(Base):
    __tablename__ = "circulars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    circular_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<Circular {self.title[:50]}>"


# ── ExamSchedules ─────────────────────────────────────────────
class ExamSchedule(Base):
    __tablename__ = "exam_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    circular_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("circulars.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    semester: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    exam_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exam_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    branch: Mapped[str | None] = mapped_column(String(100), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ExamSchedule {self.subject} sem={self.semester}>"


# ── Subscriptions ─────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel), default=NotificationChannel.EMAIL
    )
    notify_new_circular: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_exam_update: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_results: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription user={self.user_id} channel={self.channel}>"


# ── Notifications ─────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(SAEnum(NotificationChannel))
    status: Mapped[NotificationStatus] = mapped_column(
        SAEnum(NotificationStatus), default=NotificationStatus.PENDING
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification user={self.user_id} status={self.status}>"
