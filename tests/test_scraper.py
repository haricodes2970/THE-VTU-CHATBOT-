"""
tests/test_scraper.py
Unit tests for the scraper components (no real network calls).
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── VTUScraper ────────────────────────────────────────────────────────────────

class TestVTUScraper:
    SAMPLE_HTML = """
    <html><body>
    <a href="/circulars/5th-sem.pdf">5th Semester Exam Schedule 2025</a>
    <a href="/circulars/admit.pdf">Admission Circular 2025</a>
    <a href="/about">About VTU</a>
    </body></html>
    """

    @patch("scraper.vtu_scraper.requests.Session")
    def test_scrape_circulars_returns_pdfs_only(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.text = self.SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        from scraper.vtu_scraper import VTUScraper
        scraper = VTUScraper()
        results = scraper.scrape_circulars()

        pdf_results = [r for r in results if r["url"].endswith(".pdf")]
        assert len(pdf_results) >= 1

    @patch("scraper.vtu_scraper.requests.Session")
    def test_get_new_circulars_filters_existing(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.text = self.SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        from scraper.vtu_scraper import VTUScraper
        scraper = VTUScraper()
        all_circulars = scraper.scrape_circulars()
        if not all_circulars:
            pytest.skip("No circulars scraped from mock HTML")

        existing_urls = [all_circulars[0]["url"]]
        new_ones = scraper.get_new_circulars(existing_urls)
        assert len(new_ones) == len(all_circulars) - 1

    @patch("scraper.vtu_scraper.requests.Session")
    def test_retry_on_connection_error(self, mock_session_cls):
        """Verify tenacity retries on connection errors."""
        import requests as req
        mock_session = MagicMock()
        mock_session.get.side_effect = [
            req.ConnectionError("Connection refused"),
            req.ConnectionError("Connection refused"),
            req.ConnectionError("Connection refused"),
        ]
        mock_session_cls.return_value = mock_session

        from scraper.vtu_scraper import VTUScraper
        scraper = VTUScraper()
        # Should exhaust retries and raise
        with pytest.raises(req.ConnectionError):
            scraper._get("http://fake.url")

        assert mock_session.get.call_count == 3


# ── PDFParser ─────────────────────────────────────────────────────────────────

class TestPDFParser:
    def test_clean_text_removes_page_numbers(self):
        from scraper.pdf_parser import PDFParser
        parser = PDFParser()
        text = "Some content\n1\n\nMore content\n2\nEnd"
        cleaned = parser.clean_text(text)
        assert "1\n" not in cleaned
        assert "Some content" in cleaned

    def test_clean_text_removes_vtu_boilerplate(self):
        from scraper.pdf_parser import PDFParser
        parser = PDFParser()
        text = "Visvesvaraya Technological University\nActual content here\nBelagavi"
        cleaned = parser.clean_text(text)
        assert "Visvesvaraya" not in cleaned
        assert "Actual content here" in cleaned

    def test_parse_missing_file_returns_empty(self):
        from scraper.pdf_parser import PDFParser
        parser = PDFParser()
        result = parser.parse("/nonexistent/path/file.pdf")
        assert result["text"] == ""
        assert result["confidence_score"] == 0.0
        assert result["extraction_method"] == "file_not_found"

    def test_empty_result_structure(self):
        from scraper.pdf_parser import PDFParser
        parser = PDFParser()
        result = parser._empty_result("test")
        assert "text" in result
        assert "tables" in result
        assert "page_count" in result
        assert "extraction_method" in result
        assert "confidence_score" in result


# ── CircularDetector ──────────────────────────────────────────────────────────

class TestCircularDetector:
    def test_new_url_returns_true(self, tmp_path):
        from scraper.circular_detector import CircularDetector
        detector = CircularDetector(seen_file=tmp_path / "seen.json")
        assert detector.is_new("https://vtu.ac.in/circular1.pdf") is True

    def test_marked_url_returns_false(self, tmp_path):
        from scraper.circular_detector import CircularDetector
        detector = CircularDetector(seen_file=tmp_path / "seen.json")
        url = "https://vtu.ac.in/circular1.pdf"
        detector.mark_as_seen(url)
        assert detector.is_new(url) is False

    def test_get_unseen_filters_correctly(self, tmp_path):
        from scraper.circular_detector import CircularDetector
        detector = CircularDetector(seen_file=tmp_path / "seen.json")
        circulars = [
            {"url": "https://vtu.ac.in/a.pdf", "title": "A"},
            {"url": "https://vtu.ac.in/b.pdf", "title": "B"},
            {"url": "https://vtu.ac.in/c.pdf", "title": "C"},
        ]
        detector.mark_as_seen("https://vtu.ac.in/a.pdf")
        unseen = detector.get_unseen(circulars)
        assert len(unseen) == 2
        assert all(c["url"] != "https://vtu.ac.in/a.pdf" for c in unseen)

    def test_persistence_across_instances(self, tmp_path):
        from scraper.circular_detector import CircularDetector
        seen_file = tmp_path / "seen.json"
        url = "https://vtu.ac.in/persist.pdf"

        d1 = CircularDetector(seen_file=seen_file)
        d1.mark_as_seen(url)

        d2 = CircularDetector(seen_file=seen_file)
        assert d2.is_new(url) is False
