"""
scraper/vtu_scraper.py
VTU timetable scraper — fetches exam timetables from vtu.ac.in (2022 onwards).
Targets the WordPress category page for time-tables, paginating through posts.
"""
import hashlib
import random
import re
import time
from datetime import datetime
from typing import Optional

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

_ROMAN = {
    "i": 1, "ii": 2, "iii": 3, "iv": 4,
    "v": 5, "vi": 6, "vii": 7, "viii": 8,
}
_MONTH_MAP = {
    "january": "Jan", "february": "Feb", "march": "Mar", "april": "Apr",
    "may": "May", "june": "Jun", "july": "Jul", "august": "Aug",
    "september": "Sep", "october": "Oct", "november": "Nov", "december": "Dec",
    "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
    "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
    "oct": "Oct", "nov": "Nov", "dec": "Dec",
}
_MONTH_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
    r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
)


class VTUScraper:
    """Scrapes exam timetables from VTU's WordPress listing pages (2022 onwards)."""

    TIMETABLE_BASE = "https://vtu.ac.in/en/category/examination/time-table/"
    MIN_DATE = datetime(2022, 1, 1)

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ── HTTP helpers ───────────────────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
        reraise=True,
    )
    def _get(self, url: str, delay: float = 2.0) -> requests.Response:
        """GET with retry + polite delay. delay=0 for single-item processing."""
        if delay > 0:
            time.sleep(delay + random.uniform(0, 1))
        logger.info(f"Fetching: {url}")
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response

    def _get_fast(self, url: str) -> requests.Response:
        """GET with no delay — for process_next single-item calls."""
        return self._get(url, delay=0)

    # ── Date parsing ───────────────────────────────────────────────

    def _parse_iso_date(self, dt_str: str) -> Optional[datetime]:
        """Parse ISO-like datetime string (2024-06-15T...) → datetime."""
        try:
            return datetime.strptime(dt_str[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None

    def _parse_wp_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract published date from a WordPress post page."""
        time_el = soup.find(
            "time", {"class": re.compile(r"entry-date|published", re.I)}
        )
        if time_el and time_el.get("datetime"):
            result = self._parse_iso_date(time_el["datetime"])
            if result:
                return result

        meta = soup.find("meta", {"property": "article:published_time"})
        if meta and meta.get("content"):
            result = self._parse_iso_date(meta["content"])
            if result:
                return result

        return None

    def _parse_listing_date(self, card) -> Optional[datetime]:
        """Parse date from a post card on the listing page."""
        if card is None:
            return None
        time_el = card.find("time")
        if time_el and time_el.get("datetime"):
            return self._parse_iso_date(time_el["datetime"])
        return None

    # ── Main scrape method ────────────────────────────────────────

    def discover_post_urls(
        self,
        processed_post_urls: set[str],
        start_page: int = 1,
        max_pages: int = 10,
    ) -> list[str]:
        """
        FAST phase — only fetch listing pages (no individual post visits).
        Returns list of new post URLs not in processed_post_urls.
        Use start_page/max_pages to paginate across multiple HTTP calls
        (each call safely fits within Render's 30s timeout with max_pages<=5).
        """
        new_urls: list[str] = []

        for page_num in range(start_page, start_page + max_pages):
            page_url = f"{self.TIMETABLE_BASE}page/{page_num}/"
            try:
                resp = self._get(page_url, delay=0.5)  # listing pages: 0.5s is enough
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 404:
                    logger.info(f"Page {page_num} → 404, stopping pagination")
                else:
                    logger.error(f"HTTP {status} on page {page_num}: {e}")
                break
            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            post_links = soup.select("h2.entry-title a[href]")
            if not post_links:
                post_links = soup.select("article h2 a[href], .post-title a[href]")
            if not post_links:
                break

            all_pre_2022 = True
            for link_el in post_links:
                post_url = link_el["href"].strip()
                card = link_el.find_parent("article") or link_el.find_parent("li")
                pub_date = self._parse_listing_date(card)

                if pub_date and pub_date < self.MIN_DATE:
                    continue

                all_pre_2022 = False
                if post_url not in processed_post_urls:
                    new_urls.append(post_url)

            if all_pre_2022:
                logger.info(f"All posts on page {page_num} are pre-2022 — stopping")
                break

        logger.info(f"discover_post_urls: found {len(new_urls)} new post URLs")
        return new_urls

    def scrape_new_timetables(self, processed_post_urls: set[str]) -> list[dict]:
        """
        Fetches listing pages /page/1/ … /page/10/ until:
          - page returns 404, OR
          - ALL posts on the page are pre-2022.
        Skips URLs already in processed_post_urls.
        Returns list of timetable dicts for new posts only.
        """
        results: list[dict] = []

        for page_num in range(1, 11):
            page_url = f"{self.TIMETABLE_BASE}page/{page_num}/"
            try:
                resp = self._get(page_url)
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 404:
                    logger.info(f"Page {page_num} → 404, stopping pagination")
                else:
                    logger.error(f"HTTP {status} on page {page_num}: {e}")
                break
            except Exception as e:
                logger.error(f"Failed to fetch page {page_num}: {e}")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # WordPress: <h2 class="entry-title"><a href="POST_URL">
            post_links = soup.select("h2.entry-title a[href]")
            if not post_links:
                post_links = soup.select("article h2 a[href], .post-title a[href]")
            if not post_links:
                logger.warning(f"No post links on page {page_num} — stopping")
                break

            all_pre_2022 = True
            for link_el in post_links:
                post_url = link_el["href"].strip()
                title = link_el.get_text(strip=True)

                card = link_el.find_parent("article") or link_el.find_parent("li")
                pub_date = self._parse_listing_date(card)

                if pub_date and pub_date < self.MIN_DATE:
                    logger.debug(f"Pre-2022 ({pub_date.date()}): {title[:60]}")
                    continue

                all_pre_2022 = False

                if post_url in processed_post_urls:
                    logger.debug(f"Already processed: {post_url}")
                    continue

                metadata = self.extract_post_metadata(post_url, title, pub_date)
                if metadata:
                    results.append(metadata)

            if all_pre_2022:
                logger.info(f"All posts on page {page_num} are pre-2022 — stopping")
                break

        logger.info(f"scrape_new_timetables: {len(results)} new timetables found")
        return results

    def extract_post_metadata(
        self,
        post_url: str,
        post_title: str,
        published_date: Optional[datetime],
        fast: bool = False,
    ) -> Optional[dict]:
        """
        Visit a single post page, extract PDF link + metadata.
        Returns None if no PDF found or post is pre-2022.
        fast=True skips the polite delay (use for process_next single-item calls).
        """
        try:
            resp = self._get_fast(post_url) if fast else self._get(post_url)
        except Exception as e:
            logger.error(f"Failed to fetch post {post_url}: {e}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        if not published_date:
            published_date = self._parse_wp_date(soup)

        if published_date and published_date < self.MIN_DATE:
            logger.debug(f"Pre-2022 post, skipping: {post_url}")
            return None

        if not post_title:
            h1 = soup.find("h1", class_=re.compile(r"entry-title", re.I))
            post_title = h1.get_text(strip=True) if h1 else ""

        # Find PDF in .entry-content first, then anywhere on page
        pdf_url: Optional[str] = None
        content_div = soup.find(
            class_=re.compile(r"entry-content|post-content", re.I)
        )
        search_scope = content_div if content_div else soup

        for a in search_scope.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().endswith(".pdf") or "wp-content/uploads" in href:
                pdf_url = href
                break

        if not pdf_url:
            # Final fallback: any PDF anywhere on the page
            for a in soup.find_all("a", href=True):
                if a["href"].strip().lower().endswith(".pdf"):
                    pdf_url = a["href"].strip()
                    break

        if not pdf_url:
            logger.warning(f"No PDF found in post: {post_url}")
            return None

        title = post_title or "VTU Timetable"
        return {
            "post_url": post_url,
            "pdf_url": pdf_url,
            "title": title[:500],
            "published_date": published_date or datetime.utcnow(),
            "scheme": self.detect_scheme(title),
            "course_type": self.detect_course_type(title),
            "exam_session": self.extract_exam_session(title),
            "semester_range": self.extract_semester_range(title),
        }

    # ── Metadata extraction helpers ───────────────────────────────

    def detect_scheme(self, title: str) -> str:
        """Detect curriculum scheme from title string."""
        t = title.lower()
        if "2022 scheme" in t or "2022scheme" in t:
            return "2022"
        if "2021 scheme" in t or "2021scheme" in t or "(2021" in t:
            return "2021"
        if "2018 scheme" in t or "cbcs" in t or "2015" in t:
            return "2018"
        if any(x in t for x in ["m.tech", "mtech", "mba", "mca", "p.g", " pg "]):
            return "PG"
        if "ph.d" in t or "phd" in t:
            return "PhD"
        return "2021"

    def detect_course_type(self, title: str) -> str:
        """Detect course type from title."""
        t = title.lower()
        if "m.tech" in t or "mtech" in t:
            return "MTech"
        if "mba" in t:
            return "MBA"
        if "mca" in t:
            return "MCA"
        if "b.arch" in t or "barch" in t:
            return "BArch"
        if "b.plan" in t or "bplan" in t:
            return "BPlan"
        if "ph.d" in t or "phd" in t:
            return "PhD"
        return "BE/BTech"

    def extract_exam_session(self, title: str) -> str:
        """
        Normalize exam session from title for deduplication.
          "Dec 2025/Jan 2026"        → "Dec2025_3_4sem" (if sem in title)
          "June/July 2024"           → "JunJul2024"
          "Jan/Feb 2023"             → "JanFeb2023"
        """
        pattern = re.compile(
            rf"({_MONTH_PATTERN})"
            r"[\s./]*"
            rf"(?:({_MONTH_PATTERN})[\s./]*)?"
            r"(\d{{4}})",
            re.IGNORECASE,
        )
        m = pattern.search(title)
        if m:
            key1 = m.group(1).lower()[:3].capitalize()
            m1 = _MONTH_MAP.get(key1, key1)
            m2 = ""
            if m.group(2):
                key2 = m.group(2).lower()[:3].capitalize()
                m2 = _MONTH_MAP.get(key2, key2)
            year = m.group(3)
            sem_range = self.extract_semester_range(title)
            sem_suffix = (
                f"_{sem_range.replace('/', '_')}sem" if sem_range != "all" else ""
            )
            return f"{m1}{m2}{year}{sem_suffix}"

        year_m = re.search(r"20\d{2}", title)
        if year_m:
            return f"Unknown{year_m.group()}"
        return "UnknownSession"

    def extract_semester_range(self, title: str) -> str:
        """
        Extract semester range from title.
          "III/IV Semester" → "3/4"
          "I/II"            → "1/2"
          "V/VI"            → "5/6"
          "VII/VIII"        → "7/8"
          "I Semester"      → "1"
          default           → "all"
        """
        t = title.lower()

        # Roman numeral pair: III/IV, V/VI, etc.
        m = re.search(
            r"\b(viii|vii|vi|iv|v|iii|ii|i)\s*/\s*(viii|vii|vi|iv|v|iii|ii|i)\b",
            t,
            re.IGNORECASE,
        )
        if m:
            a = _ROMAN.get(m.group(1).lower())
            b = _ROMAN.get(m.group(2).lower())
            if a and b:
                return f"{a}/{b}"

        # Arabic digit pair: 3/4 sem
        m = re.search(r"\b([1-8])\s*/\s*([1-8])\s*sem", t)
        if m:
            return f"{m.group(1)}/{m.group(2)}"

        # Single roman numeral semester
        m = re.search(
            r"\b(viii|vii|vi|iv|v|iii|ii|i)\s+sem(?:ester)?",
            t,
            re.IGNORECASE,
        )
        if m:
            n = _ROMAN.get(m.group(1).lower())
            if n:
                return str(n)

        # Single arabic semester
        m = re.search(r"\b([1-8])\s*(?:st|nd|rd|th)?\s*sem(?:ester)?", t)
        if m:
            return m.group(1)

        return "all"

    def compute_pdf_hash(self, pdf_content: bytes) -> str:
        """MD5 hash of PDF bytes for change detection."""
        return hashlib.md5(pdf_content).hexdigest()
