"""
notifications/notification_manager.py
Orchestrates notifications across email and Telegram channels.
All notifications are stored in DB before sending (audit trail).
In development mode, logs instead of sending.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from loguru import logger

from backend.core.config import settings
from backend.models.models import (
    User, Circular, ExamSchedule, Subscription,
    Notification, NotificationChannel, NotificationStatus,
)
from notifications.email_notifier import EmailNotifier
from notifications.telegram_notifier import TelegramNotifier


class NotificationManager:
    """Sends and tracks notifications across all subscribed channels."""

    def __init__(self):
        self._email = EmailNotifier()
        self._telegram = TelegramNotifier()

    # ── Notify new circular ────────────────────────────────────────

    def notify_new_circular(self, circular: Circular, db: Session) -> dict:
        """
        Full workflow:
        1. Get subscribed users
        2. Create Notification records (PENDING)
        3. Send via their channels
        4. Mark SENT or FAILED
        Returns summary dict.
        """
        subscribers = self._get_subscribers(db, notify_new_circular=True)
        logger.info(
            f"Notifying {len(subscribers)} subscribers of new circular: {circular.title[:60]}"
        )

        sent, failed = 0, 0
        for user, channel in subscribers:
            notif = self._create_notification(
                db, user, channel,
                title=f"New Circular: {circular.title[:100]}",
                message=f"A new VTU circular has been published. View at: {circular.url}",
            )
            success = self._dispatch(user, channel, "circular", circular=circular)
            self._update_notification(db, notif, success)
            if success:
                sent += 1
            else:
                failed += 1

        return {"sent": sent, "failed": failed, "total": len(subscribers)}

    # ── Notify exam update ─────────────────────────────────────────

    def notify_exam_update(self, exam: ExamSchedule, db: Session) -> dict:
        """Notify users subscribed to exam updates."""
        subscribers = self._get_subscribers(db, notify_exam_update=True)
        sent, failed = 0, 0
        for user, channel in subscribers:
            # Only notify students in the same semester
            if user.semester and user.semester != exam.semester:
                continue
            notif = self._create_notification(
                db, user, channel,
                title=f"Exam Update: {exam.subject}",
                message=f"Exam: {exam.subject} | Date: {exam.exam_date} | Time: {exam.exam_time}",
            )
            success = self._dispatch(user, channel, "exam", exam=exam)
            self._update_notification(db, notif, success)
            if success:
                sent += 1
            else:
                failed += 1
        return {"sent": sent, "failed": failed}

    # ── Retry failed ──────────────────────────────────────────────

    def retry_failed(self, db: Session) -> int:
        """Retry all FAILED notifications. Returns count retried."""
        stmt = select(Notification).where(
            Notification.status == NotificationStatus.FAILED
        )
        failed_notifs = db.execute(stmt).scalars().all()
        retried = 0
        for notif in failed_notifs:
            user = db.execute(select(User).where(User.id == notif.user_id)).scalar_one_or_none()
            if not user:
                continue
            try:
                if notif.channel == NotificationChannel.EMAIL:
                    success = self._email.send(user.email, notif.title, notif.message)
                elif notif.channel == NotificationChannel.TELEGRAM and user.telegram_chat_id:
                    success = self._telegram.send_message(
                        user.telegram_chat_id,
                        f"*{notif.title}*\n{notif.message}",
                    )
                else:
                    continue
                self._update_notification(db, notif, success)
                if success:
                    retried += 1
            except Exception as e:
                logger.error(f"Retry failed for notification {notif.id}: {e}")
        return retried

    def get_pending(self, db: Session) -> list[Notification]:
        """Return all PENDING notifications."""
        stmt = select(Notification).where(
            Notification.status == NotificationStatus.PENDING
        )
        return list(db.execute(stmt).scalars().all())

    # ── Internal helpers ──────────────────────────────────────────

    def _get_subscribers(
        self,
        db: Session,
        notify_new_circular: bool = False,
        notify_exam_update: bool = False,
    ) -> list[tuple[User, NotificationChannel]]:
        """Return (user, channel) pairs for active subscribers."""
        stmt = (
            select(User, Subscription.channel)
            .join(Subscription, User.id == Subscription.user_id)
            .where(User.is_active == True)  # noqa: E712
            .where(Subscription.is_active == True)  # noqa: E712
        )
        if notify_new_circular:
            stmt = stmt.where(Subscription.notify_new_circular == True)  # noqa: E712
        if notify_exam_update:
            stmt = stmt.where(Subscription.notify_exam_update == True)  # noqa: E712

        return [(row[0], row[1]) for row in db.execute(stmt).all()]

    def _create_notification(
        self,
        db: Session,
        user: User,
        channel: NotificationChannel,
        title: str,
        message: str,
    ) -> Notification:
        notif = Notification(
            user_id=user.id,
            title=title[:500],
            message=message,
            channel=channel,
            status=NotificationStatus.PENDING,
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

    def _update_notification(
        self, db: Session, notif: Notification, success: bool
    ) -> None:
        notif.status = NotificationStatus.SENT if success else NotificationStatus.FAILED
        notif.sent_at = datetime.utcnow() if success else None
        db.commit()

    def _dispatch(
        self,
        user: User,
        channel: NotificationChannel,
        notification_type: str,
        circular: Optional[Circular] = None,
        exam: Optional[ExamSchedule] = None,
    ) -> bool:
        """Route notification to the correct channel."""
        if settings.is_development:
            logger.info(
                f"[DEV] Notification → {user.email} via {channel.value}: "
                f"type={notification_type}"
            )
            return True

        try:
            if channel == NotificationChannel.EMAIL:
                if notification_type == "circular" and circular:
                    return self._email.send_new_circular_alert(user, circular)
                elif notification_type == "exam" and exam:
                    return self._email.send_exam_reminder(user, exam)
            elif channel == NotificationChannel.TELEGRAM and user.telegram_chat_id:
                if notification_type == "circular" and circular:
                    return self._telegram.send_new_circular_alert(
                        user.telegram_chat_id, circular
                    )
                elif notification_type == "exam" and exam:
                    return self._telegram.send_exam_reminder(
                        user.telegram_chat_id, exam
                    )
        except Exception as e:
            logger.error(f"Dispatch error for {user.email} via {channel.value}: {e}")
            return False
        return False
