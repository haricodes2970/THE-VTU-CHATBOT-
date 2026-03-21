"""
scraper/pipeline.py
Incremental timetable scraping pipeline. Handles:
  - State tracking via JSON files (processed posts + PDF hash cache)
  - PDF download → text extraction → immediate deletion (no PDF kept on disk)
  - MD5 hash-based change detection (catches silent PDF updates)
  - Exam session deduplication (revised timetables detected + atomic re-indexed)
  - Atomic Pinecone replacement via VectorEmbedder.atomic_replace_circular
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

from scraper.vtu_scraper import VTUScraper
from scraper.pdf_parser import PDFParser

PROCESSED_POSTS_FILE = Path("data/raw/processed_post_urls.json")
SEEN_PDFS_FILE = Path("data/raw/seen_circulars.json")
PENDING_POSTS_FILE = Path("data/raw/pending_posts.json")
PDF_TEMP_DIR = Path("data/pdfs")
PIPELINE_LOG_FILE = Path("data/raw/pipeline_log.json")

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ── JSON state helpers ─────────────────────────────────────────

def _load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── Pipeline ───────────────────────────────────────────────────

class ScrapingPipeline:
    """
    Full timetable scraping pipeline — incremental, hash-aware, atomic re-index.
    Each PDF is downloaded → text extracted → deleted within the same call.
    No PDFs are kept on disk.
    """

    def __init__(self, db_session=None):
        self.scraper = VTUScraper()
        self.parser = PDFParser()
        self.db = db_session
        PDF_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        PROCESSED_POSTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ── State I/O (DB-primary, JSON-fallback) ─────────────────────

    def _db_load(self, key: str, default):
        """Load state from DB scrape_state table, fallback to JSON file."""
        if self.db is not None:
            try:
                from backend.models.models import ScrapeState
                row = self.db.query(ScrapeState).filter(ScrapeState.key == key).first()
                if row:
                    return json.loads(row.data)
            except Exception as e:
                logger.warning(f"DB state load failed for '{key}': {e}")
        # JSON fallback (local dev / first boot)
        file_map = {
            "pending": PENDING_POSTS_FILE,
            "processed": PROCESSED_POSTS_FILE,
            "seen_pdfs": SEEN_PDFS_FILE,
        }
        return _load_json(file_map.get(key, Path(f"data/raw/{key}.json")), default)

    def _db_save(self, key: str, data) -> None:
        """Save state to DB scrape_state table, fallback to JSON file."""
        serialized = json.dumps(data, default=str)
        if self.db is not None:
            try:
                from backend.models.models import ScrapeState
                from datetime import datetime as _dt
                row = self.db.query(ScrapeState).filter(ScrapeState.key == key).first()
                if row:
                    row.data = serialized
                    row.updated_at = _dt.utcnow()
                else:
                    self.db.add(ScrapeState(key=key, data=serialized, updated_at=_dt.utcnow()))
                self.db.commit()
                return
            except Exception as e:
                logger.warning(f"DB state save failed for '{key}': {e}")
        # JSON fallback
        file_map = {
            "pending": PENDING_POSTS_FILE,
            "processed": PROCESSED_POSTS_FILE,
            "seen_pdfs": SEEN_PDFS_FILE,
        }
        _save_json(file_map.get(key, Path(f"data/raw/{key}.json")), data)

    def _load_pending_posts(self) -> list[str]:
        return self._db_load("pending", [])

    def _save_pending_posts(self, urls: list[str]) -> None:
        self._db_save("pending", urls)

    def get_pending_count(self) -> int:
        return len(self._load_pending_posts())

    def _load_processed_posts(self) -> set[str]:
        return set(self._db_load("processed", []))

    def _save_processed_posts(self, urls: set[str]) -> None:
        self._db_save("processed", sorted(urls))

    def _load_seen_pdfs(self) -> dict[str, str]:
        """Returns {pdf_url: md5_hash}."""
        return self._db_load("seen_pdfs", {})

    def _save_seen_pdfs(self, data: dict) -> None:
        self._db_save("seen_pdfs", data)

    # ── PDF download + text extraction ────────────────────────────

    def _download_pdf(self, pdf_url: str) -> tuple[bytes, str]:
        """
        Download PDF bytes and return (content, md5_hash).
        Raises on HTTP error.
        """
        resp = requests.get(pdf_url, headers=_HTTP_HEADERS, timeout=25)
        resp.raise_for_status()
        content = resp.content
        pdf_hash = self.scraper.compute_pdf_hash(content)
        return content, pdf_hash

    def _extract_text_from_bytes(self, pdf_bytes: bytes, pdf_url: str) -> str:
        """
        Write PDF bytes to a temp file, extract text, delete temp file immediately.
        Returns extracted text (may be empty on OCR failure).
        """
        import hashlib
        fname = PDF_TEMP_DIR / f"temp_{hashlib.md5(pdf_url.encode()).hexdigest()[:12]}.pdf"
        fname.write_bytes(pdf_bytes)
        try:
            result = self.parser.parse(fname)
            return result.get("text", "")
        finally:
            if fname.exists():
                fname.unlink()
                logger.debug(f"Deleted temp PDF: {fname.name}")

    # ── DB helpers ─────────────────────────────────────────────────

    def _find_old_circular(
        self, exam_session: str, scheme: str, semester_range: str
    ) -> Optional[object]:
        """Find existing non-superseded circular with same dedup key."""
        if self.db is None:
            return None
        from backend.models.models import Circular
        return (
            self.db.query(Circular)
            .filter(
                Circular.exam_session == exam_session,
                Circular.scheme == scheme,
                Circular.semester_range == semester_range,
                Circular.is_superseded == False,  # noqa: E712
            )
            .order_by(Circular.circular_date.desc())
            .first()
        )

    def _save_circular(self, data: dict) -> Optional[object]:
        """Save circular to DB, return the saved Circular object or None."""
        if self.db is None:
            logger.warning("No DB session — skipping database save")
            return None
        try:
            from backend.services.circular_service import CircularService
            return CircularService().save_circular(self.db, data)
        except Exception as e:
            logger.error(f"DB save failed for {data.get('url')}: {e}")
            return None

    def _mark_superseded(self, old_circular, superseded_by_id: int) -> None:
        if self.db is None or old_circular is None:
            return
        old_circular.is_superseded = True
        old_circular.superseded_by_id = superseded_by_id
        old_circular.is_indexed = False
        self.db.commit()
        logger.info(
            f"Marked circular {old_circular.id} as superseded by {superseded_by_id}"
        )

    # ── Pinecone embedding ────────────────────────────────────────

    def _handle_revised_timetable(
        self, old_circular, new_circular
    ) -> bool:
        """
        Atomically replace old Pinecone vectors with new ones.
        Returns True on success; old data kept intact on failure.
        """
        if old_circular is None or new_circular is None:
            return False
        try:
            from backend.rag_pipeline.embedder import VectorEmbedder
            success = VectorEmbedder().atomic_replace_circular(
                old_circular_id=old_circular.id,
                new_circular=new_circular,
                db=self.db,
            )
            if success:
                self._mark_superseded(old_circular, new_circular.id)
            return success
        except Exception as e:
            logger.error(
                f"_handle_revised_timetable failed "
                f"[{old_circular.id}→{new_circular.id}]: {e}"
            )
            return False

    def _embed_normal(self, circular) -> None:
        """Embed a new (non-revised) circular into Pinecone main namespace."""
        try:
            from backend.rag_pipeline.embedder import VectorEmbedder
            count = VectorEmbedder().embed_circular(circular, db=self.db)
            logger.info(f"Embedded circular {circular.id}: {count} vectors")
        except Exception as e:
            logger.error(f"Embed failed for circular {getattr(circular, 'id', '?')}: {e}")

    # ── Two-phase scraping (Render-friendly) ──────────────────────

    def discover(
        self, force: bool = False, start_page: int = 1, max_pages: int = 5
    ) -> dict:
        """
        PHASE 1 — Fetches listing pages only, saves post URLs to queue.
        Defaults to max_pages=5 so each call finishes in ~15s (well within
        Render's 30s HTTP timeout). Call twice to cover all 10 pages:
          discover(force=True, start_page=1, max_pages=5)   # pages 1–5
          discover(start_page=6, max_pages=5)               # pages 6–10
        """
        processed_posts = set() if force else self._load_processed_posts()
        if force and PROCESSED_POSTS_FILE.exists():
            PROCESSED_POSTS_FILE.unlink()
            processed_posts = set()

        new_urls = self.scraper.discover_post_urls(
            processed_posts, start_page=start_page, max_pages=max_pages
        )

        # Merge with any existing pending (avoid duplicates)
        existing_pending = set(self._load_pending_posts())
        combined = list(existing_pending | set(new_urls))
        self._save_pending_posts(combined)

        logger.info(f"discover: queued {len(new_urls)} new posts ({len(combined)} total pending)")
        return {"queued": len(new_urls), "total_pending": len(combined)}

    def process_next(self, db=None, batch: int = 1) -> dict:
        """
        PHASE 2 — Processes next `batch` posts from pending_posts.json queue.
        Each post: visit post page → download PDF → extract → embed → save state.
        Call repeatedly until pending queue is empty.
        """
        if db:
            self.db = db

        pending = self._load_pending_posts()
        if not pending:
            return {"processed": 0, "remaining": 0, "message": "Queue empty — done!"}

        to_process = pending[:batch]
        remaining = pending[batch:]

        processed_posts = self._load_processed_posts()
        seen_pdfs = self._load_seen_pdfs()

        new_count = 0
        revised_count = 0
        skipped_count = 0
        errors: list[str] = []

        for post_url in to_process:
            try:
                # Visit post page and extract metadata
                metadata = self.scraper.extract_post_metadata(post_url, "", None, fast=True)
                if not metadata:
                    logger.warning(f"No metadata/PDF found for: {post_url}")
                    processed_posts.add(post_url)
                    continue

                pdf_url = metadata["pdf_url"]

                # Download PDF
                pdf_bytes, pdf_hash = self._download_pdf(pdf_url)

                existing_hash = seen_pdfs.get(pdf_url)
                if existing_hash == pdf_hash:
                    logger.info(f"PDF unchanged: {pdf_url}")
                    processed_posts.add(post_url)
                    skipped_count += 1
                    continue

                old_circular = self._find_old_circular(
                    metadata["exam_session"],
                    metadata["scheme"],
                    metadata["semester_range"],
                )
                is_revised = old_circular is not None

                text = self._extract_text_from_bytes(pdf_bytes, pdf_url)
                pdf_bytes = None

                circular_data = {
                    "title": metadata["title"],
                    "url": pdf_url,
                    "source_post_url": post_url,
                    "content": text,
                    "circular_date": metadata["published_date"],
                    "scheme": metadata["scheme"],
                    "course_type": metadata["course_type"],
                    "exam_session": metadata["exam_session"],
                    "semester_range": metadata["semester_range"],
                    "pdf_hash": pdf_hash,
                    "is_superseded": False,
                }
                new_circular = self._save_circular(circular_data)

                if is_revised:
                    success = self._handle_revised_timetable(old_circular, new_circular)
                    if success:
                        revised_count += 1
                    else:
                        errors.append(f"Atomic re-index failed: {pdf_url}")
                        if new_circular:
                            self._embed_normal(new_circular)
                        new_count += 1
                else:
                    if new_circular:
                        self._embed_normal(new_circular)
                    new_count += 1

                processed_posts.add(post_url)
                seen_pdfs[pdf_url] = pdf_hash

            except Exception as e:
                logger.error(f"process_next error for {post_url}: {e}")
                errors.append(f"{post_url}: {str(e)}")
                # Mark as processed so it doesn't re-enter the queue on next discover
                processed_posts.add(post_url)

        # Save state
        self._save_pending_posts(remaining)
        self._save_processed_posts(processed_posts)
        self._save_seen_pdfs(seen_pdfs)

        return {
            "processed": len(to_process),
            "new": new_count,
            "revised": revised_count,
            "skipped": skipped_count,
            "remaining": len(remaining),
            "errors": errors,
        }

    # ── Main incremental run ───────────────────────────────────────

    def run_incremental(self, db=None, batch_size: int = 3) -> dict:
        """
        Called every 6 hours by the scheduler.
        Returns summary dict.
        """
        if db:
            self.db = db
        start = datetime.utcnow()
        logger.info("=== ScrapingPipeline.run_incremental() started ===")

        # STEP 1: Load state
        processed_posts = self._load_processed_posts()
        seen_pdfs = self._load_seen_pdfs()

        # STEP 2: Scrape new post pages
        new_timetables = self.scraper.scrape_new_timetables(processed_posts)
        logger.info(f"Found {len(new_timetables)} new timetable posts to process")

        # Process in small batches so each HTTP request completes within Render's timeout
        new_timetables = new_timetables[:batch_size]
        logger.info(f"Processing batch of {len(new_timetables)} posts")

        new_count = 0
        revised_count = 0
        skipped_count = 0
        errors: list[str] = []

        # STEP 3: Process each new timetable
        for timetable in new_timetables:
            post_url = timetable["post_url"]
            pdf_url = timetable["pdf_url"]
            try:
                # a) Download PDF
                pdf_bytes, pdf_hash = self._download_pdf(pdf_url)

                # b) Skip if PDF content unchanged
                existing_hash = seen_pdfs.get(pdf_url)
                if existing_hash == pdf_hash:
                    logger.info(f"PDF unchanged (hash match): {pdf_url}")
                    processed_posts.add(post_url)
                    skipped_count += 1
                    continue

                # c) Dedup check: same exam session already in DB?
                old_circular = self._find_old_circular(
                    timetable["exam_session"],
                    timetable["scheme"],
                    timetable["semester_range"],
                )
                is_revised = old_circular is not None

                # d) Extract text from PDF, delete temp file immediately
                text = self._extract_text_from_bytes(pdf_bytes, pdf_url)
                pdf_bytes = None  # free memory

                # e) Save circular metadata to DB
                circular_data = {
                    "title": timetable["title"],
                    "url": pdf_url,
                    "source_post_url": post_url,
                    "content": text,
                    "circular_date": timetable["published_date"],
                    "scheme": timetable["scheme"],
                    "course_type": timetable["course_type"],
                    "exam_session": timetable["exam_session"],
                    "semester_range": timetable["semester_range"],
                    "pdf_hash": pdf_hash,
                    "is_superseded": False,
                }
                new_circular = self._save_circular(circular_data)

                # f) Embed into Pinecone (atomic if replacing old)
                if is_revised:
                    logger.info(
                        f"Revised timetable: session={timetable['exam_session']} "
                        f"scheme={timetable['scheme']} — triggering atomic re-index"
                    )
                    success = self._handle_revised_timetable(old_circular, new_circular)
                    if success:
                        revised_count += 1
                    else:
                        errors.append(f"Atomic re-index failed: {pdf_url}")
                        # Fallback: still index the new circular normally
                        if new_circular:
                            self._embed_normal(new_circular)
                        new_count += 1
                else:
                    if new_circular:
                        self._embed_normal(new_circular)
                    new_count += 1

                # g/h/i/j) Persist state after each successful item
                processed_posts.add(post_url)
                seen_pdfs[pdf_url] = pdf_hash
                self._save_processed_posts(processed_posts)
                self._save_seen_pdfs(seen_pdfs)

            except Exception as e:
                logger.error(f"Pipeline error for {post_url}: {e}")
                errors.append(f"{post_url}: {str(e)}")

        # STEP 4: Return summary
        total_vectors = 0
        try:
            from backend.rag_pipeline.embedder import VectorEmbedder
            total_vectors = VectorEmbedder().get_index_stats().get("total_vectors", 0)
        except Exception:
            pass

        duration = (datetime.utcnow() - start).total_seconds()
        summary = {
            "run_at": start.isoformat(),
            "duration_seconds": round(duration, 2),
            "new_timetables": new_count,
            "revised_timetables": revised_count,
            "skipped_unchanged": skipped_count,
            "errors": errors,
            "total_vectors_in_pinecone": total_vectors,
        }
        self._log_run(summary)
        logger.info(f"=== Pipeline complete: {summary} ===")
        return summary

    # ── Admin helpers ──────────────────────────────────────────────

    def run_force_recheck(self, db=None, batch_size: int = 3) -> dict:
        """
        Clear processed_post_urls.json so all 2022+ posts are re-visited,
        then run incremental. Use once after initial deployment.
        """
        if PROCESSED_POSTS_FILE.exists():
            PROCESSED_POSTS_FILE.unlink()
            logger.info("Cleared processed_post_urls.json for force_recheck")
        return self.run_incremental(db=db, batch_size=batch_size)

    def clear_state(self) -> list[str]:
        """Clear state from DB and JSON files. Call before a full fresh rescrape."""
        cleared = []
        # Clear DB state
        if self.db is not None:
            try:
                from backend.models.models import ScrapeState
                deleted = self.db.query(ScrapeState).delete()
                self.db.commit()
                if deleted:
                    cleared.append(f"db_scrape_state ({deleted} rows)")
                    logger.info(f"Cleared {deleted} rows from scrape_state table")
            except Exception as e:
                logger.warning(f"DB clear_state failed: {e}")
        # Also delete JSON files
        for f in [SEEN_PDFS_FILE, PROCESSED_POSTS_FILE, PENDING_POSTS_FILE]:
            if f.exists():
                f.unlink()
                cleared.append(f.name)
                logger.info(f"Deleted state file: {f.name}")
        return cleared

    def get_processed_count(self) -> int:
        return len(self._load_processed_posts())

    # ── Logging ───────────────────────────────────────────────────

    def _log_run(self, summary: dict) -> None:
        log = _load_json(PIPELINE_LOG_FILE, [])
        log.append(summary)
        _save_json(PIPELINE_LOG_FILE, log[-100:])


if __name__ == "__main__":
    from loguru import logger as _logger
    _logger.add("logs/scraper.log", rotation="10 MB")
    pipeline = ScrapingPipeline()
    result = pipeline.run_incremental()
    print(result)
