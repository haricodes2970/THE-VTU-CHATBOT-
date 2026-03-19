"""
backend/api/routes/circulars.py
Circular endpoints — list, get by ID, search, trigger scrape.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.circular_service import CircularService

router = APIRouter()
_service = CircularService()


# ── Response models ───────────────────────────────────────────────────────────

class CircularResponse(BaseModel):
    id: int
    title: str
    url: str
    pdf_path: Optional[str] = None
    content: Optional[str] = None
    circular_date: Optional[str] = None
    is_processed: bool
    is_indexed: bool
    scraped_at: str

    model_config = {"from_attributes": True}


class CircularListResponse(BaseModel):
    circulars: list[CircularResponse]
    total: int
    page: int
    limit: int


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/circulars",
    response_model=CircularListResponse,
    summary="List all circulars",
    description="Returns a paginated list of VTU circulars. Use `search` to filter by title.",
)
def list_circulars(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if limit > 50:
        limit = 50
    if search:
        rows = _service.search_circulars(db, search, page, limit)
        total = len(rows)
    else:
        rows, total = _service.get_all_circulars(db, page, limit)

    return CircularListResponse(
        circulars=[
            CircularResponse(
                id=c.id,
                title=c.title,
                url=c.url,
                pdf_path=c.pdf_path,
                content=c.content,
                circular_date=str(c.circular_date) if c.circular_date else None,
                is_processed=c.is_processed,
                is_indexed=c.is_indexed,
                scraped_at=str(c.scraped_at),
            )
            for c in rows
        ],
        total=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/circulars/{circular_id}",
    response_model=CircularResponse,
    summary="Get a single circular by ID",
)
def get_circular(circular_id: int, db: Session = Depends(get_db)):
    circular = _service.get_circular_by_id(db, circular_id)
    if not circular:
        raise HTTPException(status_code=404, detail=f"Circular {circular_id} not found")
    return CircularResponse(
        id=circular.id,
        title=circular.title,
        url=circular.url,
        pdf_path=circular.pdf_path,
        content=circular.content,
        circular_date=str(circular.circular_date) if circular.circular_date else None,
        is_processed=circular.is_processed,
        is_indexed=circular.is_indexed,
        scraped_at=str(circular.scraped_at),
    )


def _run_scrape():
    """Background task: run incremental scraping pipeline."""
    from scraper.pipeline import ScrapingPipeline
    ScrapingPipeline().run_incremental()


@router.post(
    "/circulars/trigger-scrape",
    summary="Manually trigger the scraping pipeline (admin)",
    description="Kicks off an incremental scrape in the background.",
)
def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_scrape)
    return {"message": "Scraping pipeline triggered in background"}
