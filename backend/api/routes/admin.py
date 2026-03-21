"""
backend/api/routes/admin.py
Admin-only endpoints protected by X-Admin-Key header.
"""
from fastapi import APIRouter, Depends, HTTPException, Header, BackgroundTasks, Request
from pydantic import BaseModel
from typing import Optional
from loguru import logger

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
    "/admin/discover",
    summary="Phase 1: Discover new post URLs from VTU listing pages (admin)",
    dependencies=[Depends(_require_admin)],
)
def discover_posts(force: bool = False, start_page: int = 1, max_pages: int = 5):
    """
    Fetches VTU timetable listing pages and saves new post URLs to a queue.
    Defaults to max_pages=5 so it finishes within Render's 30s timeout.
    Call twice to cover all 10 pages:
      POST /admin/discover?force=true&start_page=1&max_pages=5
      POST /admin/discover&start_page=6&max_pages=5
    force=true clears processed history and re-discovers all 2022+ posts.
    State is stored in the DB (survives redeploys).
    """
    from backend.core.database import SessionLocal
    from scraper.pipeline import ScrapingPipeline
    db = SessionLocal()
    try:
        pipeline = ScrapingPipeline(db_session=db)
        result = pipeline.discover(force=force, start_page=start_page, max_pages=max_pages)
        return result
    finally:
        db.close()


@router.post(
    "/admin/process-next",
    summary="Phase 2: Process next post(s) from queue (admin)",
    dependencies=[Depends(_require_admin)],
)
def process_next(batch: int = 1, embed: bool = False, skip_pdf: bool = True):
    """
    Visits next `batch` posts in queue and saves to DB.
    skip_pdf=true (default): use post body HTML text — fast, ~10-15s per post.
    skip_pdf=false: download + parse PDF — slow, ~35-55s per post (may OOM).
    embed=false (default): skip Pinecone embedding. Use /admin/embed-pending after.
    embed=true: also embed into Pinecone (adds 30-120s per post).
    """
    from backend.core.database import SessionLocal
    from scraper.pipeline import ScrapingPipeline
    db = SessionLocal()
    try:
        pipeline = ScrapingPipeline(db_session=db)
        result = pipeline.process_next(
            db=db, batch=min(batch, 5), embed=embed, skip_pdf=skip_pdf
        )
        return result
    finally:
        db.close()


@router.post(
    "/admin/embed-pending",
    summary="Embed next unindexed circular(s) into Pinecone (admin)",
    dependencies=[Depends(_require_admin)],
)
def embed_pending(batch: int = 1):
    """
    Embeds next `batch` unindexed circulars from DB into Pinecone.
    Call repeatedly until all circulars are indexed.
    Each call takes 30-120s (fastembed + Pinecone upsert).
    """
    from backend.core.database import SessionLocal
    from backend.models.models import Circular
    from backend.rag_pipeline.embedder import VectorEmbedder
    db = SessionLocal()
    try:
        circulars = (
            db.query(Circular)
            .filter(Circular.is_indexed == False, Circular.is_superseded == False)  # noqa: E712
            .limit(min(batch, 3))
            .all()
        )
        if not circulars:
            return {"embedded": 0, "message": "All circulars already indexed"}
        embedder = VectorEmbedder()
        embedded = 0
        errors = []
        for c in circulars:
            try:
                count = embedder.embed_circular(c, db=db)
                embedded += 1
                logger.info(f"Embedded circular {c.id}: {count} vectors")
            except Exception as e:
                errors.append(f"circular {c.id}: {str(e)}")
                logger.error(f"Embed failed for circular {c.id}: {e}")
        remaining = (
            db.query(Circular)
            .filter(Circular.is_indexed == False, Circular.is_superseded == False)  # noqa: E712
            .count()
        )
        return {"embedded": embedded, "remaining_unindexed": remaining, "errors": errors}
    finally:
        db.close()


@router.post(
    "/admin/trigger-scrape",
    summary="Trigger timetable scraping pipeline (admin)",
    dependencies=[Depends(_require_admin)],
)
def trigger_scrape(body: TriggerScrapeRequest = TriggerScrapeRequest()):
    """
    incremental   → run Phase 1 discover only (call process-next separately)
    force_recheck → clear state + run Phase 1 discover (call process-next separately)
    """
    if body.mode not in ("incremental", "force_recheck"):
        raise HTTPException(status_code=400, detail="mode must be 'incremental' or 'force_recheck'")

    from backend.core.database import SessionLocal
    from scraper.pipeline import ScrapingPipeline
    db = SessionLocal()
    try:
        pipeline = ScrapingPipeline(db_session=db)
        result = pipeline.discover(force=(body.mode == "force_recheck"))
        return {"status": "discovered", "mode": body.mode, "result": result}
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
    Clears scrape state (pending queue, processed URLs, seen PDFs) from DB + JSON files.
    Call this before discover with force=true to start fresh.
    """
    from backend.core.database import SessionLocal
    from scraper.pipeline import ScrapingPipeline
    db = SessionLocal()
    try:
        cleared = ScrapingPipeline(db_session=db).clear_state()
        return {"cleared": cleared}
    finally:
        db.close()


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

    db2 = SessionLocal()
    try:
        pipeline_inst = ScrapingPipeline(db_session=db2)
        processed_post_count = pipeline_inst.get_processed_count()
        pending_post_count = pipeline_inst.get_pending_count()
    finally:
        db2.close()

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
        "pending_in_queue": pending_post_count,
        "last_scrape_run": last_run,
    }


# ── Debug: ScrapeState table contents ────────────────────────

@router.get(
    "/admin/debug-state",
    summary="Show raw ScrapeState DB table contents (admin)",
    dependencies=[Depends(_require_admin)],
)
def debug_state():
    """Returns what is actually stored in the scrape_state DB table."""
    from backend.core.database import SessionLocal
    db = SessionLocal()
    try:
        from backend.models.models import ScrapeState
        rows = db.query(ScrapeState).all()
        result = {}
        for row in rows:
            import json as _json
            try:
                data = _json.loads(row.data)
                count = len(data) if isinstance(data, (list, dict)) else "n/a"
            except Exception:
                count = "parse_error"
            result[row.key] = {"count": count, "updated_at": str(row.updated_at)}
        return {"table_exists": True, "rows": result}
    except Exception as e:
        return {"table_exists": False, "error": str(e)}
    finally:
        db.close()


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
        import requests
        from bs4 import BeautifulSoup
        resp = requests.get(
            VTUScraper.TIMETABLE_BASE,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        links = soup.select("h2.entry-title a[href]")
        posts = [{"url": a["href"], "title": a.get_text(strip=True)[:80]} for a in links[:5]]
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
