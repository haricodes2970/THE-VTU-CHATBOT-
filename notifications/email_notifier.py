"""
notifications/email_notifier.py
Sends email notifications via SMTP (Gmail). HTML templates included inline.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.config import settings


def _html_new_circular(circular_title: str, circular_url: str, date: str) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px">
    <div style="background:#2563EB;padding:20px;border-radius:8px 8px 0 0">
      <h2 style="color:white;margin:0">📢 New VTU Circular</h2>
    </div>
    <div style="border:1px solid #e5e7eb;padding:20px;border-radius:0 0 8px 8px">
      <h3 style="color:#1f2937">{circular_title}</h3>
      <p style="color:#6b7280">Published: {date}</p>
      <a href="{circular_url}" style="background:#2563EB;color:white;padding:10px 20px;
         border-radius:6px;text-decoration:none;display:inline-block;margin-top:10px">
        View Circular →
      </a>
      <hr style="margin-top:20px;border:none;border-top:1px solid #e5e7eb">
      <p style="color:#9ca3af;font-size:12px">
        VTU Smart Scheduler · <a href="https://vtu.ac.in">vtu.ac.in</a>
      </p>
    </div>
    </body></html>
    """


def _html_exam_reminder(subject: str, exam_date: str, exam_time: str, semester: int) -> str:
    return f"""
    <html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;padding:20px">
    <div style="background:#16a34a;padding:20px;border-radius:8px 8px 0 0">
      <h2 style="color:white;margin:0">📅 Exam Reminder</h2>
    </div>
    <div style="border:1px solid #e5e7eb;padding:20px;border-radius:0 0 8px 8px">
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:8px;color:#6b7280;font-weight:bold">Subject</td>
            <td style="padding:8px;color:#1f2937">{subject}</td></tr>
        <tr style="background:#f9fafb">
            <td style="padding:8px;color:#6b7280;font-weight:bold">Semester</td>
            <td style="padding:8px;color:#1f2937">{semester}</td></tr>
        <tr><td style="padding:8px;color:#6b7280;font-weight:bold">Date</td>
            <td style="padding:8px;color:#dc2626;font-weight:bold">{exam_date}</td></tr>
        <tr style="background:#f9fafb">
            <td style="padding:8px;color:#6b7280;font-weight:bold">Time</td>
            <td style="padding:8px;color:#1f2937">{exam_time}</td></tr>
      </table>
      <p style="color:#4b5563;margin-top:15px">
        📌 Carry your hall ticket and valid ID. Report 30 minutes before the exam.
      </p>
      <hr style="margin-top:20px;border:none;border-top:1px solid #e5e7eb">
      <p style="color:#9ca3af;font-size:12px">VTU Smart Scheduler</p>
    </div>
    </body></html>
    """


class EmailNotifier:
    """Sends HTML emails via SMTP (Gmail). Retries 3 times on failure."""

    def _build_message(
        self, to: str, subject: str, body: str, html: Optional[str] = None
    ) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.email_from or settings.smtp_user
        msg["To"] = to
        msg.attach(MIMEText(body, "plain"))
        if html:
            msg.attach(MIMEText(html, "html"))
        return msg

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        reraise=True,
    )
    def send(
        self, to: str, subject: str, body: str, html: Optional[str] = None
    ) -> bool:
        """Send an email. Returns True on success."""
        if not settings.smtp_user or not settings.smtp_password:
            logger.warning("SMTP not configured — skipping email send")
            return False

        msg = self._build_message(to, subject, body, html)
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(settings.smtp_user, to, msg.as_string())
            logger.info(f"Email sent to {to}: '{subject}'")
            return True
        except Exception as e:
            # Never log passwords
            logger.error(f"Email send failed to {to}: {type(e).__name__}: {e}")
            raise

    def send_new_circular_alert(self, user, circular) -> bool:
        """Send a 'new circular' alert email to a user."""
        date_str = str(circular.circular_date.date()) if circular.circular_date else "N/A"
        return self.send(
            to=user.email,
            subject=f"[VTU] New Circular: {circular.title[:60]}",
            body=(
                f"Hi {user.name},\n\nA new VTU circular has been published:\n"
                f"{circular.title}\n\nView: {circular.url}\n\nVTU Smart Scheduler"
            ),
            html=_html_new_circular(circular.title, circular.url, date_str),
        )

    def send_exam_reminder(self, user, exam_schedule) -> bool:
        """Send an exam reminder email."""
        return self.send(
            to=user.email,
            subject=f"[VTU] Exam Reminder: {exam_schedule.subject}",
            body=(
                f"Hi {user.name},\n\nReminder: {exam_schedule.subject} exam\n"
                f"Date: {exam_schedule.exam_date}\nTime: {exam_schedule.exam_time}\n"
                f"Semester: {exam_schedule.semester}\n\nVTU Smart Scheduler"
            ),
            html=_html_exam_reminder(
                exam_schedule.subject,
                str(exam_schedule.exam_date),
                exam_schedule.exam_time or "TBA",
                exam_schedule.semester or "N/A",
            ),
        )
