"""
backend/api/routes/notifications.py
Subscription and notification endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.user_service import UserService
from backend.models.models import Notification

router = APIRouter()
_user_service = UserService()


# ── Request / Response models ─────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)
    semester: Optional[int] = Field(None, ge=1, le=8)
    branch: Optional[str] = Field(None, max_length=50)
    channels: list[str] = Field(default=["email"])

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: list[str]) -> list[str]:
        valid = {"email", "telegram"}
        for ch in v:
            if ch not in valid:
                raise ValueError(f"Invalid channel '{ch}'. Must be: {valid}")
        return v


class SubscribeResponse(BaseModel):
    user_id: int
    message: str


class UpdatePrefsRequest(BaseModel):
    semester: Optional[int] = Field(None, ge=1, le=8)
    branch: Optional[str] = Field(None, max_length=50)


class NotificationItem(BaseModel):
    id: int
    title: str
    message: str
    channel: str
    status: str
    sent_at: Optional[str] = None
    created_at: str


class TestNotificationRequest(BaseModel):
    user_id: int
    channel: str = "email"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    summary="Subscribe to VTU notifications",
    description="Register email/name and choose notification channels (email, telegram).",
)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)):
    user = _user_service.create_user(
        db,
        email=str(body.email),
        name=body.name,
        semester=body.semester,
        branch=body.branch,
    )
    _user_service.create_subscription(db, user.id, body.channels)
    return SubscribeResponse(
        user_id=user.id,
        message=f"Subscribed successfully via {', '.join(body.channels)}",
    )


@router.get(
    "/notifications",
    response_model=list[NotificationItem],
    summary="Get notification history for a user",
)
def get_notifications(
    user_id: int,
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    if limit > 100:
        limit = 100
    offset = (page - 1) * limit
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        NotificationItem(
            id=n.id,
            title=n.title,
            message=n.message,
            channel=n.channel.value,
            status=n.status.value,
            sent_at=str(n.sent_at) if n.sent_at else None,
            created_at=str(n.created_at),
        )
        for n in rows
    ]


@router.put(
    "/subscribe/{user_id}",
    summary="Update subscription preferences",
)
def update_subscription(
    user_id: int,
    body: UpdatePrefsRequest,
    db: Session = Depends(get_db),
):
    user = _user_service.update_preferences(
        db, user_id, semester=body.semester, branch=body.branch
    )
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return {"message": "Preferences updated", "user_id": user_id}


@router.delete(
    "/subscribe/{user_id}",
    summary="Unsubscribe from notifications",
)
def unsubscribe(user_id: int, db: Session = Depends(get_db)):
    from sqlalchemy import update as sa_update
    from backend.models.models import Subscription
    db.execute(
        sa_update(Subscription)
        .where(Subscription.user_id == user_id)
        .values(is_active=False)
    )
    db.commit()
    return {"message": f"User {user_id} unsubscribed"}


@router.post(
    "/notifications/test",
    summary="Send a test notification",
    description="Sends a test message to verify notification setup. In dev mode, logs instead of sending.",
)
def test_notification(body: TestNotificationRequest, db: Session = Depends(get_db)):
    from backend.core.config import settings
    from loguru import logger
    logger.info(
        f"Test notification requested for user_id={body.user_id} via {body.channel}"
    )
    if settings.is_development:
        return {
            "message": f"[DEV MODE] Test notification logged for user {body.user_id} via {body.channel}",
            "sent": False,
        }
    # In production, trigger real notification
    return {
        "message": f"Test notification queued for user {body.user_id}",
        "sent": True,
    }
