"""
scraper/pdf_parser.py
Lightweight PDF text extractor using pypdf.
Designed for Render free tier (512MB RAM limit).
"""
import io
import re
import hashlib
from typing import Optional
import requests
from pypdf import PdfReader
from loguru import logger


class PDFParser:
    """
    Memory-efficient PDF parser using pypdf.
    Extracts text from URL or local file.
    Total RAM usage: ~15MB per PDF (vs 230MB with pdfplumber+tesseract).
    """

    MAX_FILE_SIZE_MB = 10
    REQUEST_TIMEOUT = 30

    def extract_from_url(self, pdf_url: str) -> dict:
        """
        Download PDF from URL, extract text, return result.
        NEVER saves PDF to disk — streams entirely in memory.
        """
        try:
            response = requests.get(
                pdf_url,
                timeout=self.REQUEST_TIMEOUT,
                stream=True,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()

            content_length = response.headers.get("Content-Length")
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > self.MAX_FILE_SIZE_MB:
                    logger.warning(f"PDF too large ({size_mb:.1f}MB), skipping: {pdf_url}")
                    return self._error_result(f"File too large: {size_mb:.1f}MB")

            pdf_bytes = response.content
            size_mb = len(pdf_bytes) / (1024 * 1024)
            pdf_hash = hashlib.md5(pdf_bytes).hexdigest()

            logger.info(f"Downloaded PDF: {size_mb:.1f}MB from {pdf_url}")

            text, page_count = self._extract_text(pdf_bytes)
            del pdf_bytes  # free RAM immediately

            if not text.strip():
                logger.warning(f"Empty text extracted from {pdf_url}")
                return {
                    "text": "",
                    "page_count": page_count,
                    "pdf_hash": pdf_hash,
                    "extraction_method": "pypdf",
                    "success": False,
                    "error": "No text extracted — PDF may be image-based",
                    "file_size_mb": round(size_mb, 2),
                }

            cleaned = self.clean_text(text)
            logger.info(f"Extracted {len(cleaned)} chars from {page_count} pages")

            return {
                "text": cleaned,
                "page_count": page_count,
                "pdf_hash": pdf_hash,
                "extraction_method": "pypdf",
                "success": True,
                "error": None,
                "file_size_mb": round(size_mb, 2),
            }

        except requests.Timeout:
            return self._error_result("Download timeout")
        except requests.HTTPError as e:
            return self._error_result(f"HTTP error: {e}")
        except Exception as e:
            logger.error(f"PDF parse error for {pdf_url}: {e}")
            return self._error_result(str(e))

    def _extract_text(self, pdf_bytes: bytes) -> tuple[str, int]:
        """Extract text from PDF bytes using pypdf."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return "\n".join(pages), len(reader.pages)

    def clean_text(self, raw_text: str) -> str:
        """Clean extracted PDF text for embedding."""
        if not raw_text:
            return ""

        lines = raw_text.split("\n")
        cleaned_lines = []
        seen_lines = set()

        boilerplate = [
            "visvesvaraya technological university",
            "vtu.ac.in",
            "belgaum", "belagavi",
            "jnana sangama",
            "phone:", "fax:",
            "registrar",
        ]

        for line in lines:
            line = line.strip()
            if not line or len(line) < 3:
                continue
            line_lower = line.lower()
            if any(bp in line_lower for bp in boilerplate):
                continue
            if line_lower in seen_lines:
                continue
            seen_lines.add(line_lower)
            # Fix spacing in date columns: "12 /12 /2025" → "12/12/2025"
            line = re.sub(r'(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', r'\1/\2/\3', line)
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def extract_exam_dates_from_text(self, text: str) -> list[dict]:
        """
        Extract structured exam date entries from timetable text.
        Returns list of {subject_code, subject_name, date, time, session}.
        """
        results = []

        pattern1 = re.compile(
            r'([A-Z0-9]{4,8})\s+'
            r'([A-Za-z][^\d]{5,50}?)\s+'
            r'(\d{1,2}/\d{1,2}/\d{4})\s+'
            r'(FN|AN|10:00|14:00|02:00)',
            re.IGNORECASE
        )
        pattern2 = re.compile(r'\b(\d{1,2}/\d{1,2}/\d{4})\b')

        for match in pattern1.finditer(text):
            code, name, date, session = match.groups()
            time_str = "10:00 AM" if session.upper() in ("FN", "10:00") else "2:00 PM"
            results.append({
                "subject_code": code.strip(),
                "subject_name": name.strip(),
                "date": date.strip(),
                "time": time_str,
                "session": session.strip(),
            })

        if not results:
            for match in pattern2.finditer(text):
                results.append({
                    "subject_code": None,
                    "subject_name": "Unknown",
                    "date": match.group(1),
                    "time": "10:00 AM",
                    "session": "FN",
                })

        logger.info(f"Extracted {len(results)} exam date entries from text")
        return results

    def _error_result(self, error_msg: str) -> dict:
        return {
            "text": "",
            "page_count": 0,
            "pdf_hash": "",
            "extraction_method": "pypdf",
            "success": False,
            "error": error_msg,
            "file_size_mb": 0,
        }
