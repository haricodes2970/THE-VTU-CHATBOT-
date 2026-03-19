"""
scraper/pipeline.py
Orchestrates the full scraping pipeline: scrape → download → parse → save to DB.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from scraper.vtu_scraper import VTUScraper
from scraper.pdf_downloader import PDFDownloader
from scraper.pdf_parser import PDFParser
from scraper.circular_detector import CircularDetector

PIPELINE_LOG_FILE = Path("./data/raw/pipeline_log.json")


class ScrapingPipeline:
    """
    Full scraping pipeline:
    scrape → download PDFs → parse text → save to database.
    """

    def __init__(self, db_session=None):
        self.scraper = VTUScraper()
        self.downloader = PDFDownloader()
        self.parser = PDFParser()
        self.detector = CircularDetector()
        self.db = db_session
        PIPELINE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _save_to_db(self, circular_data: dict) -> None:
        """Persist circular to PostgreSQL if db session is available."""
        if self.db is None:
            logger.warning("No DB session — skipping database save")
            return
        try:
            from backend.services.circular_service import CircularService
            CircularService().save_circular(self.db, circular_data)
        except Exception as e:
            logger.error(f"DB save failed for {circular_data.get('url')}: {e}")

    def _log_run(self, summary: dict) -> None:
        log: list = []
        if PIPELINE_LOG_FILE.exists():
            try:
                log = json.loads(PIPELINE_LOG_FILE.read_text(encoding="utf-8"))
            except Exception:
                log = []
        log.append(summary)
        # Keep last 100 runs
        PIPELINE_LOG_FILE.write_text(
            json.dumps(log[-100:], indent=2, default=str), encoding="utf-8"
        )

    # ── Full run ──────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Full pipeline run: scrape ALL circulars, download, parse, and save.
        Returns a summary dict.
        """
        start = datetime.utcnow()
        logger.info("=== ScrapingPipeline.run() started ===")

        circulars = self.scraper.scrape_circulars()
        logger.info(f"Found {len(circulars)} circulars total")

        saved, failed, skipped = 0, 0, 0

        for circular in circulars:
            url = circular["url"]
            try:
                # Download PDF
                pdf_path = self.downloader.download_pdf(url)
                if pdf_path:
                    result = self.parser.parse(pdf_path)
                    circular["pdf_path"] = str(pdf_path)
                    circular["content"] = result["text"]
                else:
                    circular["pdf_path"] = None
                    circular["content"] = None

                self._save_to_db(circular)
                self.detector.mark_as_seen(url)
                saved += 1
            except Exception as e:
                logger.error(f"Pipeline error for {url}: {e}")
                failed += 1

        duration = (datetime.utcnow() - start).total_seconds()
        summary = {
            "run_at": start.isoformat(),
            "type": "full",
            "total_found": len(circulars),
            "saved": saved,
            "failed": failed,
            "skipped": skipped,
            "duration_seconds": round(duration, 2),
        }
        self._log_run(summary)
        logger.info(f"=== Pipeline complete: {summary} ===")
        return summary

    # ── Incremental run ───────────────────────────────────────────

    def run_incremental(self) -> dict:
        """
        Only process circulars not yet seen. Faster for scheduled runs.
        """
        start = datetime.utcnow()
        logger.info("=== ScrapingPipeline.run_incremental() started ===")

        all_circulars = self.scraper.scrape_circulars()
        new_circulars = self.detector.get_unseen(all_circulars)

        if not new_circulars:
            logger.info("No new circulars found")
            summary = {
                "run_at": start.isoformat(),
                "type": "incremental",
                "total_found": len(all_circulars),
                "new_found": 0,
                "saved": 0,
                "failed": 0,
                "duration_seconds": 0,
            }
            self._log_run(summary)
            return summary

        saved, failed = 0, 0
        for circular in new_circulars:
            url = circular["url"]
            try:
                pdf_path = self.downloader.download_pdf(url)
                if pdf_path:
                    result = self.parser.parse(pdf_path)
                    circular["pdf_path"] = str(pdf_path)
                    circular["content"] = result["text"]
                else:
                    circular["pdf_path"] = None
                    circular["content"] = None

                self._save_to_db(circular)
                self.detector.mark_as_seen(url)
                saved += 1
            except Exception as e:
                logger.error(f"Incremental pipeline error for {url}: {e}")
                failed += 1

        duration = (datetime.utcnow() - start).total_seconds()
        summary = {
            "run_at": start.isoformat(),
            "type": "incremental",
            "total_found": len(all_circulars),
            "new_found": len(new_circulars),
            "saved": saved,
            "failed": failed,
            "duration_seconds": round(duration, 2),
        }
        self._log_run(summary)
        logger.info(f"=== Incremental pipeline complete: {summary} ===")
        return summary


if __name__ == "__main__":
    from loguru import logger
    logger.add("logs/scraper.log", rotation="10 MB")
    pipeline = ScrapingPipeline()
    result = pipeline.run_incremental()
    print(result)
