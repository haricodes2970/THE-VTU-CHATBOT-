"""
scraper/vtu_scraper.py
VTU website scraper — fetches circulars and exam schedule links from vtu.ac.in.
"""
import hashlib
import time
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 30
RATE_LIMIT_SECONDS = 2


class VTUScraper:
    """Scrapes circulars and exam schedule links from the VTU website."""

    def __init__(
        self,
        base_url: str = "https://vtu.ac.in",
        circulars_url: str = "https://vtu.ac.in/circulars",
    ):
        self.base_url = base_url
        self.circulars_url = circulars_url
        self._last_page_hash: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ── Internal helpers ──────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _get(self, url: str) -> requests.Response:
        """GET request with retry logic."""
        logger.info(f"Fetching: {url}")
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        time.sleep(RATE_LIMIT_SECONDS)
        return response

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Try to parse a date string into a datetime object."""
        formats = ["%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %B %Y", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None

    # ── Public methods ────────────────────────────────────────────

    def scrape_circulars(self) -> list[dict]:
        """
        Scrape circulars from the VTU circulars page.
        Returns list of dicts with: title, url, date, category.
        """
        circulars: list[dict] = []
        try:
            resp = self._get(self.circulars_url)
            soup = BeautifulSoup(resp.text, "lxml")

            # VTU typically lists circulars in <a> tags inside tables or divs
            # We look for PDF links and surrounding text
            for link in soup.find_all("a", href=True):
                href = link["href"].strip()
                if not href.lower().endswith(".pdf"):
                    continue

                # Make absolute URL
                if not href.startswith("http"):
                    href = self.base_url.rstrip("/") + "/" + href.lstrip("/")

                title = link.get_text(strip=True) or link.get("title", "")
                if not title:
                    # Try parent element text
                    parent = link.find_parent()
                    title = parent.get_text(strip=True)[:200] if parent else ""

                # Try to find a date near the link
                parent_text = ""
                if link.parent:
                    parent_text = link.parent.get_text(" ", strip=True)

                date_obj = None
                import re
                date_match = re.search(
                    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}", parent_text
                )
                if date_match:
                    date_obj = self._parse_date(date_match.group())

                circulars.append({
                    "title": title[:500],
                    "url": href,
                    "date": date_obj,
                    "category": "general",
                })

            logger.info(f"Scraped {len(circulars)} circulars from {self.circulars_url}")
        except requests.HTTPError as e:
            logger.error(f"HTTP error scraping circulars: {e}")
        except Exception as e:
            logger.error(f"Unexpected error scraping circulars: {e}")

        return circulars

    def scrape_exam_schedules(self) -> list[dict]:
        """
        Scrape exam schedule PDF links from VTU website.
        Returns list of dicts with: title, url, date.
        """
        schedules: list[dict] = []
        exam_urls = [
            f"{self.base_url}/exam-time-table",
            f"{self.base_url}/examination",
        ]

        for url in exam_urls:
            try:
                resp = self._get(url)
                soup = BeautifulSoup(resp.text, "lxml")

                for link in soup.find_all("a", href=True):
                    href = link["href"].strip()
                    if not href.lower().endswith(".pdf"):
                        continue
                    if not href.startswith("http"):
                        href = self.base_url.rstrip("/") + "/" + href.lstrip("/")

                    title = link.get_text(strip=True) or "Exam Schedule"
                    schedules.append({"title": title[:500], "url": href, "date": None})

                logger.info(f"Found {len(schedules)} exam schedule links at {url}")
            except Exception as e:
                logger.warning(f"Could not scrape {url}: {e}")

        return schedules

    def get_new_circulars(self, existing_urls: list[str]) -> list[dict]:
        """
        Return only circulars whose URLs are not already in existing_urls.
        """
        all_circulars = self.scrape_circulars()
        existing_set = set(existing_urls)
        new_ones = [c for c in all_circulars if c["url"] not in existing_set]
        logger.info(f"Found {len(new_ones)} new circulars (out of {len(all_circulars)} total)")
        return new_ones

    def detect_changes(self) -> bool:
        """
        Returns True if the circulars page has changed since last check,
        using a hash of the page content.
        """
        try:
            resp = self._get(self.circulars_url)
            page_hash = hashlib.md5(resp.content).hexdigest()
            if self._last_page_hash is None:
                self._last_page_hash = page_hash
                return True  # first run — treat as change
            changed = page_hash != self._last_page_hash
            self._last_page_hash = page_hash
            if changed:
                logger.info("VTU circulars page has changed")
            return changed
        except Exception as e:
            logger.error(f"Error detecting changes: {e}")
            return False
