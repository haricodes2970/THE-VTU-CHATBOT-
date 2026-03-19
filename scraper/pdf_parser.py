"""
scraper/pdf_parser.py
Extracts text and tables from PDF files using pdfplumber (primary),
PyPDF2 (fallback), and pytesseract OCR (last resort for scanned PDFs).
"""
import io
import re
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None  # type: ignore

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class PDFParser:
    """Extracts text and structured table data from PDF files."""

    # ── Primary extraction (pdfplumber) ──────────────────────────

    def extract_text(self, pdf_path: str | Path) -> Optional[str]:
        """Extract text using pdfplumber (handles layout-aware PDFs best)."""
        if pdfplumber is None:
            logger.warning("pdfplumber not installed")
            return None
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_text = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages_text)
            logger.debug(f"pdfplumber extracted {len(text)} chars from {pdf_path}")
            return text if text.strip() else None
        except Exception as e:
            logger.warning(f"pdfplumber failed on {pdf_path}: {e}")
            return None

    # ── Fallback (PyPDF2) ─────────────────────────────────────────

    def extract_with_pypdf2(self, pdf_path: str | Path) -> Optional[str]:
        """Fallback text extraction using PyPDF2."""
        if PyPDF2 is None:
            return None
        try:
            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                if reader.is_encrypted:
                    logger.warning(f"PDF is encrypted: {pdf_path}")
                    return None
                pages_text = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages_text)
            logger.debug(f"PyPDF2 extracted {len(text)} chars from {pdf_path}")
            return text if text.strip() else None
        except Exception as e:
            logger.warning(f"PyPDF2 failed on {pdf_path}: {e}")
            return None

    # ── OCR fallback ──────────────────────────────────────────────

    def extract_with_ocr(self, pdf_path: str | Path) -> Optional[str]:
        """Last-resort OCR extraction for scanned/image-only PDFs."""
        if not OCR_AVAILABLE:
            logger.warning("pytesseract/Pillow not available for OCR")
            return None
        if pdfplumber is None:
            return None
        try:
            texts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    img = page.to_image(resolution=200).original
                    text = pytesseract.image_to_string(img, lang="eng")
                    texts.append(text)
            result = "\n".join(texts)
            logger.debug(f"OCR extracted {len(result)} chars from {pdf_path}")
            return result if result.strip() else None
        except Exception as e:
            logger.warning(f"OCR failed on {pdf_path}: {e}")
            return None

    # ── Table extraction ──────────────────────────────────────────

    def extract_tables(self, pdf_path: str | Path) -> list[list[list[str]]]:
        """
        Extract tables from PDF using pdfplumber.
        Returns a list of tables; each table is a list of rows (list of cell strings).
        """
        if pdfplumber is None:
            return []
        tables = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)
        except Exception as e:
            logger.warning(f"Table extraction failed on {pdf_path}: {e}")
        return tables

    # ── Text cleaning ─────────────────────────────────────────────

    def clean_text(self, raw_text: str) -> str:
        """Remove headers/footers, page numbers, extra whitespace, and boilerplate."""
        if not raw_text:
            return ""

        lines = raw_text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            # Skip short lines that look like page numbers
            if re.fullmatch(r"\d{1,3}", stripped):
                continue
            # Skip common VTU letterhead boilerplate
            if re.search(
                r"visvesvaraya technological university|belgaum|belagavi|vtu\.ac\.in",
                stripped,
                re.IGNORECASE,
            ):
                continue
            cleaned.append(stripped)

        text = "\n".join(cleaned)
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multiple spaces
        text = re.sub(r" {2,}", " ", text)
        return text.strip()

    # ── Page count ────────────────────────────────────────────────

    def _get_page_count(self, pdf_path: str | Path) -> int:
        if pdfplumber is None:
            return 0
        try:
            with pdfplumber.open(pdf_path) as pdf:
                return len(pdf.pages)
        except Exception:
            return 0

    # ── Main parse method ─────────────────────────────────────────

    def parse(self, pdf_path: str | Path) -> dict:
        """
        Try all extraction methods in order. Returns structured result:
        {text, tables, page_count, extraction_method, confidence_score}
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return self._empty_result("file_not_found")

        page_count = self._get_page_count(pdf_path)
        tables = self.extract_tables(pdf_path)

        # Try pdfplumber first
        text = self.extract_text(pdf_path)
        if text and len(text.strip()) > 50:
            return {
                "text": self.clean_text(text),
                "tables": tables,
                "page_count": page_count,
                "extraction_method": "pdfplumber",
                "confidence_score": 0.9,
            }

        # Fallback to PyPDF2
        text = self.extract_with_pypdf2(pdf_path)
        if text and len(text.strip()) > 50:
            return {
                "text": self.clean_text(text),
                "tables": tables,
                "page_count": page_count,
                "extraction_method": "pypdf2",
                "confidence_score": 0.7,
            }

        # Last resort: OCR
        text = self.extract_with_ocr(pdf_path)
        if text and len(text.strip()) > 50:
            return {
                "text": self.clean_text(text),
                "tables": tables,
                "page_count": page_count,
                "extraction_method": "ocr",
                "confidence_score": 0.5,
            }

        logger.error(f"All extraction methods failed for {pdf_path}")
        return self._empty_result("all_failed")

    def _empty_result(self, method: str) -> dict:
        return {
            "text": "",
            "tables": [],
            "page_count": 0,
            "extraction_method": method,
            "confidence_score": 0.0,
        }
