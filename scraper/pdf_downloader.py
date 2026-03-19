"""
scraper/pdf_downloader.py
Downloads PDF files from VTU website, avoiding duplicates and verifying integrity.
"""
import hashlib
import os
from pathlib import Path
from typing import Optional

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 60
DEFAULT_PDF_DIR = Path("./data/pdfs")


class PDFDownloader:
    """Downloads and manages PDF files from URLs."""

    def __init__(self, download_dir: str | Path = DEFAULT_PDF_DIR):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(HEADERS)

    # ── Helpers ──────────────────────────────────────────────────

    def _url_to_filename(self, url: str) -> str:
        """Convert a URL to a safe local filename."""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        # Take last path segment as base name
        base = url.rstrip("/").split("/")[-1]
        # Remove unsafe chars
        safe_base = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
        if not safe_base.lower().endswith(".pdf"):
            safe_base += ".pdf"
        return f"{url_hash}_{safe_base}"

    def _is_valid_pdf(self, path: Path) -> bool:
        """Check PDF magic bytes (25 50 44 46 = %PDF)."""
        try:
            with open(path, "rb") as f:
                header = f.read(4)
            return header == b"%PDF"
        except Exception:
            return False

    # ── Core download ─────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def download_pdf(self, url: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        Download a single PDF from url to self.download_dir.
        Returns local path on success, None on failure.
        """
        if self.is_already_downloaded(url):
            existing = self.download_dir / self._url_to_filename(url)
            logger.info(f"Already downloaded: {existing.name}")
            return existing

        fname = filename or self._url_to_filename(url)
        dest = self.download_dir / fname

        try:
            logger.info(f"Downloading: {url}")
            resp = self._session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
            resp.raise_for_status()

            content_type = resp.headers.get("Content-Type", "")
            if "pdf" not in content_type.lower() and not url.lower().endswith(".pdf"):
                logger.warning(f"Unexpected content-type '{content_type}' for {url}")

            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

            if not self._is_valid_pdf(dest):
                logger.error(f"Downloaded file is not a valid PDF: {dest}")
                dest.unlink(missing_ok=True)
                return None

            size_kb = downloaded / 1024
            logger.info(f"Saved {dest.name} ({size_kb:.1f} KB)")
            return dest

        except requests.HTTPError as e:
            logger.error(f"HTTP {e.response.status_code} downloading {url}")
            dest.unlink(missing_ok=True)
            return None
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            dest.unlink(missing_ok=True)
            return None

    def download_batch(self, pdf_urls: list[str]) -> dict[str, Optional[Path]]:
        """
        Download multiple PDFs. Returns mapping of url → local path (or None on failure).
        """
        results: dict[str, Optional[Path]] = {}
        total = len(pdf_urls)
        for i, url in enumerate(pdf_urls, 1):
            logger.info(f"[{i}/{total}] Processing {url}")
            results[url] = self.download_pdf(url)
        successful = sum(1 for v in results.values() if v is not None)
        logger.info(f"Batch complete: {successful}/{total} downloaded successfully")
        return results

    def is_already_downloaded(self, url: str) -> bool:
        """Check if the PDF for this URL is already on disk."""
        fname = self._url_to_filename(url)
        path = self.download_dir / fname
        return path.exists() and self._is_valid_pdf(path)
