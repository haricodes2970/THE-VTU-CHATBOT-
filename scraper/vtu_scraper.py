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
REQUEST_TIMEOUT = 15

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
        """
        GET with no delay and NO retry — for process_next single-item calls.
        Fails fast on timeout (no 3-retry loop that could burn 60s+).
        """
        logger.info(f"Fetching (fast): {url}")
        response = self.session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response

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
            # Try multiple selectors — VTU WordPress theme varies
            h1 = (
                soup.find("h1", class_=re.compile(r"entry-title|post-title", re.I))
                or soup.find("h1")
            )
            if h1:
                post_title = h1.get_text(strip=True)
            else:
                # Fall back to <title> tag (WordPress: "Post Title – Site Name")
                title_tag = soup.find("title")
                if title_tag:
                    raw = title_tag.get_text(strip=True)
                    post_title = raw.split("–")[0].split("|")[0].strip()
                else:
                    post_title = ""

        # Find PDF in .entry-content first, then anywhere on page
        pdf_url: Optional[str] = None
        content_div = soup.find(
            class_=re.compile(r"entry-content|post-content", re.I)
        )
        search_scope = content_div if content_div else soup

        for a in search_scope.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().endswith(".pdf"):
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

        # Extract post body text (lighter than downloading + parsing the PDF)
        post_body = ""
        if content_div:
            # Remove script/style tags, get readable text
            for tag in content_div.find_all(["script", "style"]):
                tag.decompose()
            post_body = content_div.get_text(separator="\n", strip=True)[:5000]

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
            "post_body": post_body,  # extracted from HTML (no PDF needed)
        }

    # ── Metadata extraction helpers ───────────────────────────────

    def detect_scheme(self, title: str) -> str:
        """Detect VTU scheme from post title."""
        import re
        # 1. Explicit year pattern (most reliable)
        m = re.search(r'\b(2015|2017|2018|2021|2022|2023|2024|2025)\b', title)
        if m:
            return m.group(1)
        # 2. CBCS → 2018
        if re.search(r'\bCBCS\b', title, re.IGNORECASE):
            return "2018"
        # 3. PG programmes
        if re.search(r'(?<![A-Za-z])M\.?Tech\.?(?![A-Za-z])|(?<![A-Za-z])MBA(?![A-Za-z])|(?<![A-Za-z])MCA(?![A-Za-z])|(?<![A-Za-z])P\.?G\.?(?![A-Za-z])|(?<![A-Za-z])PGCISM(?![A-Za-z])', title, re.IGNORECASE):
            return "PG"
        # 4. PhD
        if re.search(r'\bPh\.?D\.?\b', title, re.IGNORECASE):
            return "PhD"
        # 5. Default
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
        """Extract exam session from VTU post title."""
        import re

        MONTH_ABBR = {
            "january": "Jan", "february": "Feb", "march": "Mar",
            "april": "Apr", "may": "May", "june": "Jun",
            "july": "Jul", "august": "Aug", "september": "Sep",
            "october": "Oct", "november": "Nov", "december": "Dec",
            "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
            "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
            "oct": "Oct", "nov": "Nov", "dec": "Dec",
        }

        ABBR_MAP = {
            "JJ": "Jun", "DJ": "Dec", "JF": "Jan",
            "ND": "Nov", "MJ": "Mar", "AM": "Apr",
        }

        def expand_year(y: str) -> str:
            if len(y) == 2:
                return "20" + y
            return y

        # Step 1 — Month name pattern: "Dec 2025", "June/July 2024", "Jan/Feb 2023"
        m = re.search(
            r'(?<![A-Za-z])(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
            r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
            r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
            r'[a-z]*'
            r'(?:[\s/]+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|'
            r'Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|'
            r'Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)[a-z]*)?'
            r'[\s/_]*(\d{4}|\d{2})(?![0-9])',
            title, re.IGNORECASE
        )
        if m:
            month_raw = m.group(1)[:3].capitalize()
            abbr = MONTH_ABBR.get(month_raw.lower(), month_raw)
            year = expand_year(m.group(2))
            return f"{abbr}{year}"

        # Step 2 — Filename abbreviation: "JJ25", "DJ25", "JF23", "ND23"
        m = re.search(r'(?<![A-Za-z])(JJ|DJ|JF|ND|MJ|AM)(\d{2})(?![0-9])', title)
        if m:
            abbr = ABBR_MAP.get(m.group(1), "Jan")
            year = expand_year(m.group(2))
            return f"{abbr}{year}"

        # Step 3 — Underscore date: "Dec25_Jan26", "D25J26"
        m = re.search(r'\b(Dec|Jan|Jun|Nov|Mar|Apr)(\d{2})(?:_|/)(?:Jan|Feb|Jul|Jun)\d{2}', title, re.IGNORECASE)
        if m:
            abbr = m.group(1).capitalize()
            year = expand_year(m.group(2))
            return f"{abbr}{year}"

        return "UnknownSession"

    def extract_semester_range(self, title: str) -> str:
        """Extract semester range from VTU post title."""
        import re

        ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
                 "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}

        def roman_to_int(r: str) -> int:
            return ROMAN.get(r.upper(), 0)

        # Step 1 — Roman pair with slash: "III/IV Sem"
        m = re.search(
            r'\b(VIII|VII|VI|IV|V|III|II|I|IX|X)\s*/\s*(VIII|VII|VI|IV|V|III|II|I|IX|X)\s*[Ss]em',
            title
        )
        if m:
            a, b = roman_to_int(m.group(1)), roman_to_int(m.group(2))
            if a and b:
                return f"{a}/{b}"

        # Step 2 — "X and Y Semester"
        m = re.search(
            r'\b(VIII|VII|VI|IV|V|III|II|I|IX|X)\s+and\s+(VIII|VII|VI|IV|V|III|II|I|IX|X)\s*[Ss]em',
            title, re.IGNORECASE
        )
        if m:
            a, b = roman_to_int(m.group(1)), roman_to_int(m.group(2))
            if a and b:
                return f"{a}/{b}"

        # Step 3 — Digit pair with slash: "3/4 Sem"
        m = re.search(r'\b(\d)\s*/\s*(\d)\s*[Ss]em', title)
        if m:
            return f"{m.group(1)}/{m.group(2)}"

        # Step 4 — Underscore filename pattern: "_3_4SEM"
        m = re.search(r'_(\d)_(\d)[Ss][Ee][Mm]', title)
        if m:
            return f"{m.group(1)}/{m.group(2)}"

        # Step 5 — Single Roman numeral semester
        m = re.search(
            r'\b(VIII|VII|VI|IV|V|III|II|I|IX|X)\s+[Ss]em',
            title
        )
        if m:
            n = roman_to_int(m.group(1))
            if n:
                return str(n)

        # Step 6 — Ordinal digit: "6th Semester", "5th sem"
        m = re.search(r'\b(\d+)(?:st|nd|rd|th)\s+[Ss]em', title)
        if m:
            return m.group(1)

        # Step 7 — Plain digit semester: "6 Semester"
        m = re.search(r'\b(\d)\s+[Ss]em', title)
        if m:
            return m.group(1)

        return "all"

    def compute_pdf_hash(self, pdf_content: bytes) -> str:
        """MD5 hash of PDF bytes for change detection."""
        return hashlib.md5(pdf_content).hexdigest()
