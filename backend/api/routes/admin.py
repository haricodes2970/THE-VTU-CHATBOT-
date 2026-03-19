"""
backend/api/routes/admin.py
Admin-only endpoints protected by X-Admin-Key header.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks, Request
from typing import Optional

from backend.core.config import settings

router = APIRouter()


def _require_admin(x_admin_key: Optional[str] = Header(None)):
    """Dependency: validates X-Admin-Key against settings.secret_key."""
    if not x_admin_key or x_admin_key != settings.secret_key:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Admin-Key header")


@router.post(
    "/admin/trigger-scrape",
    summary="Trigger scraping pipeline immediately (admin)",
    dependencies=[Depends(_require_admin)],
)
def trigger_scrape(background_tasks: BackgroundTasks):
    from backend.services.scheduler_service import _job_scrape_and_process
    background_tasks.add_task(_job_scrape_and_process)
    return {"message": "Scraping pipeline triggered"}


@router.post(
    "/admin/reindex-all",
    summary="Re-embed all circulars into Pinecone (admin)",
    dependencies=[Depends(_require_admin)],
)
def reindex_all(background_tasks: BackgroundTasks):
    def _reindex():
        from backend.rag_pipeline.rag_chain import RAGChain
        from backend.core.database import SessionLocal
        db = SessionLocal()
        try:
            result = RAGChain().index_all_pending(db)
            from loguru import logger
            logger.info(f"Reindex complete: {result}")
        finally:
            db.close()

    background_tasks.add_task(_reindex)
    return {"message": "Reindexing started in background"}


@router.get(
    "/admin/scheduler-status",
    summary="Get scheduler job statuses (admin)",
    dependencies=[Depends(_require_admin)],
)
def scheduler_status(request: Request):
    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        return {"jobs": [], "message": "Scheduler not running"}
    return {"jobs": scheduler.get_job_status()}


@router.post(
    "/admin/retry-notifications",
    summary="Retry all failed notifications (admin)",
    dependencies=[Depends(_require_admin)],
)
def retry_notifications():
    from backend.services.scheduler_service import _job_retry_notifications
    _job_retry_notifications()
    return {"message": "Retry notifications complete"}
