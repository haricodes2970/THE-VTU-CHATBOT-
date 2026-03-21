"""
backend/api/routes/admin.py
Admin-only endpoints protected by X-Admin-Key header.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional

from backend.core.config import settings

router = APIRouter()


def _require_admin(x_admin_key: Optional[str] = Header(None)):
    """Dependency: validates X-Admin-Key against settings.secret_key."""
    if not x_admin_key or x_admin_key != settings.secret_key:
        raise HTTPException(
            status_code=403, detail="Invalid or missing X-Admin-Key header"
        )


# ── Scraper trigger ────────────────────────────────────────────

class TriggerScrapeRequest(BaseModel):
    mode: str = "incremental"  # "incremental" | "force_recheck"


@router.post(
    "/admin/trigger-scrape",
    summary="Trigger timetable scraping pipeline (admin)",
    dependencies=[Depends(_require_admin)],
)
def trigger_scrape(body: TriggerScrapeRequest = TriggerScrapeRequest()):
    """
    incremental   → discover new posts and process up to 5 at a time (call repeatedly)
    force_recheck → clears state then processes up to 5 posts (call repeatedly until done)

    Designed to be called repeatedly — each call processes the next batch of posts.
    Check /admin/scrape-stats to track progress.
    """
    if body.mode not in ("incremental", "force_recheck"):
        raise HTTPException(
            status_code=400,
            detail="mode must be 'incremental' or 'force_recheck'",
        )

    from backend.core.database import SessionLocal
    from scraper.pipeline import ScrapingPipeline
    db = SessionLocal()
    try:
        pipeline = ScrapingPipeline(db_session=db)
        if body.mode == "force_recheck":
            result = pipeline.run_force_recheck(db=db)
        else:
            result = pipeline.run_incremental(db=db)
        return {"status": "done", "mode": body.mode, "result": result}
    finally:
        db.close()


# ── Clear state ────────────────────────────────────────────────

@router.post(
    "/admin/clear-state",
    summary="Delete scraper state files for a fresh rescrape (admin)",
    dependencies=[Depends(_require_admin)],
)
def clear_state():
    """
    Deletes seen_circulars.json and processed_post_urls.json.
    Call this before trigger-scrape with mode=force_recheck.
    """
    from scraper.pipeline import ScrapingPipeline
    cleared = ScrapingPipeline().clear_state()
    return {"cleared": cleared}


# ── Scrape stats ───────────────────────────────────────────────

@router.get(
    "/admin/scrape-stats",
    summary="Scraping and indexing stats (admin)",
    dependencies=[Depends(_require_admin)],
)
def scrape_stats():
    """Returns counts of circulars, vectors, and state file sizes."""
    from backend.core.database import SessionLocal
    from backend.services.circular_service import CircularService
    from backend.rag_pipeline.embedder import VectorEmbedder
    from scraper.pipeline import ScrapingPipeline, PIPELINE_LOG_FILE, _load_json
    from sqlalchemy import func, select
    from backend.models.models import Circular

    db = SessionLocal()
    try:
        svc = CircularService()
        total = db.execute(select(func.count(Circular.id))).scalar() or 0
        superseded = svc.get_superseded_count(db)
        active = svc.get_active_timetables_count(db)
    finally:
        db.close()

    pinecone_count = 0
    try:
        pinecone_count = VectorEmbedder().get_index_stats().get("total_vectors", 0)
    except Exception:
        pass

    processed_post_count = ScrapingPipeline().get_processed_count()

    last_run = None
    log = _load_json(PIPELINE_LOG_FILE, [])
    if log:
        last_run = log[-1].get("run_at")

    return {
        "total_circulars": total,
        "superseded": superseded,
        "active_timetables": active,
        "pinecone_vector_count": pinecone_count,
        "processed_post_urls": processed_post_count,
        "last_scrape_run": last_run,
    }


# ── Debug scraper test ────────────────────────────────────────

@router.get(
    "/admin/test-scraper",
    summary="Test scraper fetches one page (admin)",
    dependencies=[Depends(_require_admin)],
)
def test_scraper():
    """Fetches page 1 of VTU timetable listings and returns what it finds. No DB writes."""
    try:
        from scraper.vtu_scraper import VTUScraper
        scraper = VTUScraper()
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(
            VTUScraper.TIMETABLE_BASE,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select("h2.entry-title a[href]")
        posts = [{"url": l["href"], "title": l.get_text(strip=True)[:80]} for l in links[:5]]
        return {
            "status": "ok",
            "http_status": resp.status_code,
            "posts_found": len(links),
            "sample": posts,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ── Existing endpoints ─────────────────────────────────────────

@router.post(
    "/admin/reindex-all",
    summary="Re-embed all unindexed circulars into Pinecone (admin)",
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
