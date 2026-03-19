"""
backend/services/text_processor.py
Processes raw circular text: cleaning, date/subject extraction, schedule structuring.
"""
import re
from datetime import datetime
from typing import Optional

from loguru import logger
from python_dateutil.parser import parse as dateutil_parse

# ── Date patterns ─────────────────────────────────────────────────────────────
_DATE_PATTERNS = [
    r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",            # DD/MM/YYYY or DD-MM-YYYY
    r"\b(\d{4}-\d{2}-\d{2})\b",                          # YYYY-MM-DD
    r"\b(\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4})\b",    # 5th June 2025
    r"\b(\w+\s+\d{1,2},?\s+\d{4})\b",                   # June 5, 2025
]

# ── Subject code pattern ──────────────────────────────────────────────────────
_SUBJECT_CODE_PATTERN = re.compile(
    r"\b([A-Z]{2,4}\d{2,3}[A-Z]?)\b"  # e.g. CS301, BCS401
)

# ── VTU boilerplate lines to remove ──────────────────────────────────────────
_BOILERPLATE = [
    r"visvesvaraya technological university",
    r"belagavi|belgaum",
    r"vtu\.ac\.in",
    r"phone\s*:\s*[\d\s-]+",
    r"fax\s*:\s*[\d\s-]+",
    r"dr\.\s*\w+\s+\w+",        # Vice Chancellor name line
    r"registrar",
    r"to all the principals",
    r"copy forwarded",
    r"ref\s*no\b",
]


class TextProcessor:
    """Cleans and structures raw circular text for downstream NLP and RAG."""

    # ── Cleaning ──────────────────────────────────────────────────

    def clean(self, raw_text: str) -> str:
        """Remove headers, footers, page numbers, VTU boilerplate, extra whitespace."""
        if not raw_text:
            return ""
        lines = raw_text.splitlines()
        cleaned = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            if re.fullmatch(r"\d{1,3}", s):  # page numbers
                continue
            if any(re.search(pat, s, re.IGNORECASE) for pat in _BOILERPLATE):
                continue
            cleaned.append(s)
        text = "\n".join(cleaned)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    # ── Date extraction ───────────────────────────────────────────

    def extract_exam_dates(self, text: str) -> list[dict]:
        """
        Find all date patterns in text and return structured list.
        Each entry: {date_str, parsed_date, context}
        """
        results: list[dict] = []
        seen: set[str] = set()

        for pattern in _DATE_PATTERNS:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                date_str = m.group(1).strip()
                if date_str in seen:
                    continue
                seen.add(date_str)

                parsed: Optional[datetime] = None
                try:
                    parsed = dateutil_parse(date_str, dayfirst=True)
                except Exception:
                    pass

                # Extract surrounding context (50 chars each side)
                start = max(0, m.start() - 50)
                end = min(len(text), m.end() + 50)
                context = text[start:end].replace("\n", " ").strip()

                results.append({
                    "date_str": date_str,
                    "parsed_date": parsed,
                    "context": context,
                })

        return results

    # ── Subject extraction ────────────────────────────────────────

    def extract_subjects(self, text: str) -> list[dict]:
        """
        Find subject names and codes in text.
        Returns list of {subject_name, subject_code, semester}
        """
        subjects: list[dict] = []
        for m in _SUBJECT_CODE_PATTERN.finditer(text):
            code = m.group(1)
            # Try to find subject name after the code
            snippet = text[m.end():m.end() + 60]
            name_match = re.match(r"[\s:\-–]+([A-Za-z &/]+)", snippet)
            name = name_match.group(1).strip() if name_match else ""

            subjects.append({
                "subject_code": code,
                "subject_name": name[:100],
                "semester": None,
            })
        return subjects

    # ── Semester info ─────────────────────────────────────────────

    def extract_semester_info(self, text: str) -> list[int]:
        """Return list of semester numbers mentioned in the text."""
        semesters: set[int] = set()
        for m in re.finditer(
            r"\b(\d)[stndrh]{0,2}\s*sem(?:ester)?\b", text, re.IGNORECASE
        ):
            val = int(m.group(1))
            if 1 <= val <= 8:
                semesters.add(val)
        return sorted(semesters)

    # ── Exam schedule table → structured data ────────────────────

    def structure_exam_schedule(self, text: str) -> list[dict]:
        """
        For exam schedule PDFs, parse table rows into structured entries.
        Returns list of {subject, date, time, semester}
        """
        schedule: list[dict] = []
        # Pattern: subject code / name followed by date and optional time
        row_pattern = re.compile(
            r"([A-Z][A-Za-z &/]{3,50})\s+"           # subject name
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"       # date
            r"(?:\s+([\d:apmAPM\s]+))?"               # optional time
        )
        for m in row_pattern.finditer(text):
            schedule.append({
                "subject": m.group(1).strip(),
                "date": m.group(2).strip(),
                "time": (m.group(3) or "").strip() or None,
                "semester": None,
            })
        return schedule

    # ── Circular type classification ──────────────────────────────

    def _classify_circular(self, text: str) -> str:
        t = text.lower()
        if re.search(r"time.?table|exam\s+schedule|examination\s+schedule", t):
            return "EXAM_SCHEDULE"
        if re.search(r"result|marks?|passed|failed|revaluation", t):
            return "RESULT"
        if re.search(r"admission|application|registration\s+fee", t):
            return "ADMISSION"
        return "GENERAL"

    # ── Master pipeline ───────────────────────────────────────────

    def process_circular(self, raw_text: str) -> dict:
        """
        Full processing pipeline for a circular.
        Returns: {cleaned_text, exam_dates, subjects, semesters, circular_type}
        """
        cleaned = self.clean(raw_text)
        circular_type = self._classify_circular(cleaned)

        exam_dates = self.extract_exam_dates(cleaned)
        subjects = self.extract_subjects(cleaned)
        semesters = self.extract_semester_info(cleaned)

        return {
            "cleaned_text": cleaned,
            "exam_dates": exam_dates,
            "subjects": subjects,
            "semesters": semesters,
            "circular_type": circular_type,
        }
