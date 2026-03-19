"""
backend/services/scheduler_service.py
APScheduler-based background job scheduler.
Jobs: scrape, retry notifications, cleanup sessions, health check.
"""
import os
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from loguru import logger

from backend.core.config import settings


def _job_scrape_and_process():
    """Run incremental scrape, embed new circulars, notify users."""
    logger.info("[Scheduler] scrape_and_process job starting")
    try:
        from scraper.pipeline import ScrapingPipeline
        from backend.core.database import SessionLocal
        from backend.rag_pipeline.rag_chain import RAGChain
        from notifications.notification_manager import NotificationManager

        db = SessionLocal()
        try:
            pipeline = ScrapingPipeline(db_session=db)
            summary = pipeline.run_incremental()
            logger.info(f"[Scheduler] Scrape complete: {summary}")

            if summary.get("saved", 0) > 0:
                rag = RAGChain()
                index_result = rag.index_all_pending(db)
                logger.info(f"[Scheduler] Indexed: {index_result}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Scheduler] scrape_and_process failed: {e}")


def _job_retry_notifications():
    """Retry all FAILED notification records."""
    logger.info("[Scheduler] retry_failed_notifications starting")
    try:
        from notifications.notification_manager import NotificationManager
        from backend.core.database import SessionLocal
        db = SessionLocal()
        try:
            count = NotificationManager().retry_failed(db)
            logger.info(f"[Scheduler] Retried {count} notifications")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[Scheduler] retry_notifications failed: {e}")


def _job_cleanup_sessions():
    """Remove expired conversation sessions."""
    logger.info("[Scheduler] cleanup_old_sessions starting")
    try:
        from backend.services.chat_service import _conv_manager
        removed = _conv_manager.cleanup_expired()
        logger.info(f"[Scheduler] Removed {removed} expired sessions")
    except Exception as e:
        logger.error(f"[Scheduler] cleanup_sessions failed: {e}")


def _job_keep_alive():
    """Ping own /health endpoint every 10 minutes to prevent Render spin-down."""
    try:
        import requests as req
        url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")
        req.get(f"{url}/health", timeout=10)
        logger.debug("[Scheduler] keep_alive ping sent")
    except Exception as e:
        logger.debug(f"[Scheduler] keep_alive ping failed (non-critical): {e}")


def _job_health_check():
    """Log DB + Pinecone health status hourly."""
    logger.info("[Scheduler] health_check_log starting")
    try:
        from backend.core.database import check_db_connection
        db_ok = check_db_connection()
        logger.info(f"[Scheduler] DB: {'OK' if db_ok else 'FAIL'}")

        import psutil
        mem = psutil.virtual_memory()
        logger.info(f"[Scheduler] Memory: {mem.percent}% used ({mem.available // 1024 // 1024}MB free)")
    except Exception as e:
        logger.error(f"[Scheduler] health_check failed: {e}")


_JOB_MAP = {
    "scrape_and_process": _job_scrape_and_process,
    "retry_notifications": _job_retry_notifications,
    "cleanup_sessions": _job_cleanup_sessions,
    "health_check": _job_health_check,
    "keep_alive": _job_keep_alive,
}


class SchedulerService:
    """Manages background jobs using APScheduler."""

    def __init__(self):
        jobstores = {}
        try:
            jobstores["default"] = SQLAlchemyJobStore(url=settings.database_url)
        except Exception:
            logger.warning("SQLAlchemy job store unavailable — using in-memory store")

        self._scheduler = BackgroundScheduler(
            jobstores=jobstores if jobstores else None,
            executors={"default": ThreadPoolExecutor(4)},
            job_defaults={"coalesce": True, "max_instances": 1},
        )

    def start(self) -> None:
        """Register all jobs and start the scheduler."""
        interval_hours = settings.scraper_interval_hours

        self._scheduler.add_job(
            _job_scrape_and_process,
            trigger="interval",
            hours=interval_hours,
            id="scrape_and_process",
            replace_existing=True,
            next_run_time=None,  # don't run immediately on startup
        )
        self._scheduler.add_job(
            _job_retry_notifications,
            trigger="interval",
            minutes=30,
            id="retry_notifications",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_cleanup_sessions,
            trigger="interval",
            hours=2,
            id="cleanup_sessions",
            replace_existing=True,
        )
        self._scheduler.add_job(
            _job_health_check,
            trigger="interval",
            hours=1,
            id="health_check",
            replace_existing=True,
        )

        self._scheduler.add_job(
            _job_keep_alive,
            trigger="interval",
            minutes=10,
            id="keep_alive",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info(
            f"Scheduler started: {len(self._scheduler.get_jobs())} jobs registered"
        )

    def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def run_now(self, job_name: str) -> bool:
        """Trigger a job immediately by name."""
        func = _JOB_MAP.get(job_name)
        if not func:
            logger.warning(f"Unknown job: {job_name}")
            return False
        logger.info(f"Manually triggering job: {job_name}")
        try:
            func()
            return True
        except Exception as e:
            logger.error(f"Manual job {job_name} failed: {e}")
            return False

    def get_job_status(self) -> list[dict]:
        """Return list of jobs with last_run, next_run, status."""
        jobs = []
        for job in self._scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs
