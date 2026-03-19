"""
notifications/telegram_notifier.py
Sends Telegram messages via python-telegram-bot (synchronous wrapper).
"""
import asyncio
from typing import Optional

from loguru import logger

from backend.core.config import settings


def _run_async(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class TelegramNotifier:
    """Sends Telegram messages using python-telegram-bot."""

    def __init__(self):
        self._bot = None

    def _get_bot(self):
        if self._bot is None:
            if not settings.telegram_bot_token:
                raise ValueError("TELEGRAM_BOT_TOKEN not configured")
            from telegram import Bot
            self._bot = Bot(token=settings.telegram_bot_token)
        return self._bot

    async def _send_async(self, chat_id: str, text: str, parse_mode: str = "Markdown") -> bool:
        try:
            bot = self._get_bot()
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            return True
        except Exception as e:
            logger.error(f"Telegram send failed to {chat_id}: {type(e).__name__}: {e}")
            return False

    def send_message(self, chat_id: str, message: str) -> bool:
        """Send a plain text message to a Telegram chat."""
        if not settings.telegram_bot_token:
            logger.warning("Telegram not configured — skipping send")
            return False
        return _run_async(self._send_async(chat_id, message))

    def send_new_circular_alert(self, chat_id: str, circular) -> bool:
        """Send a formatted circular alert to Telegram."""
        date_str = str(circular.circular_date.date()) if circular.circular_date else "N/A"
        msg = (
            f"📢 *New VTU Circular*\n\n"
            f"*{circular.title}*\n"
            f"📅 Date: {date_str}\n"
            f"🔗 [View Circular]({circular.url})\n\n"
            f"_VTU Smart Scheduler_"
        )
        return self.send_message(chat_id, msg)

    def send_exam_reminder(self, chat_id: str, exam_schedule) -> bool:
        """Send an exam reminder to Telegram."""
        msg = (
            f"📅 *Exam Reminder*\n\n"
            f"*Subject:* {exam_schedule.subject}\n"
            f"*Semester:* {exam_schedule.semester}\n"
            f"*Date:* *{exam_schedule.exam_date}*\n"
            f"*Time:* {exam_schedule.exam_time or 'TBA'}\n\n"
            f"📌 Carry your hall ticket and valid ID.\n"
            f"_VTU Smart Scheduler_"
        )
        return self.send_message(chat_id, msg)
