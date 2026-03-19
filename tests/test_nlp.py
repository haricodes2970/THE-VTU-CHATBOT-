"""
tests/test_nlp.py
Unit tests for IntentDetector, EntityExtractor, and TextProcessor.
"""
import pytest

from ai.query_processing.intent_detector import IntentDetector, Intent
from ai.query_processing.entity_extractor import EntityExtractor
from backend.services.text_processor import TextProcessor


# ── IntentDetector ────────────────────────────────────────────────────────────

class TestIntentDetector:
    detector = IntentDetector()

    @pytest.mark.parametrize("query,expected_intent", [
        ("When is my 5th sem DBMS exam?", Intent.GET_EXAM_DATE),
        ("what date is the physics exam", Intent.GET_EXAM_DATE),
        ("show me 5th sem schedule", Intent.GET_EXAM_SCHEDULE),
        ("all exams for 3rd semester", Intent.GET_EXAM_SCHEDULE),
        ("timetable for CSE 6th sem", Intent.GET_EXAM_SCHEDULE),
        ("latest circular from VTU", Intent.GET_CIRCULAR),
        ("any new notifications today", Intent.GET_CIRCULAR),
        ("are results declared?", Intent.GET_RESULTS),
        ("CIE results for 5th sem", Intent.GET_RESULTS),
        ("hello", Intent.GREETING),
        ("hi there!", Intent.GREETING),
        ("what is the fee structure", Intent.GENERAL_QUERY),
        ("tell me about VTU", Intent.GENERAL_QUERY),
        ("DBMS EXAM DATE 5TH SEM", Intent.GET_EXAM_DATE),
        ("exam schedule please", Intent.GET_EXAM_SCHEDULE),
    ])
    def test_intent_detection(self, query, expected_intent):
        result = self.detector.detect(query)
        assert result["intent"] == expected_intent, (
            f"Query: '{query}' → got {result['intent']}, expected {expected_intent}"
        )

    def test_confidence_between_0_and_1(self):
        result = self.detector.detect("when is my exam?")
        assert 0.0 <= result["confidence"] <= 1.0

    def test_raw_query_preserved(self):
        q = "When is DBMS exam?"
        result = self.detector.detect(q)
        assert result["raw_query"] == q


# ── EntityExtractor ───────────────────────────────────────────────────────────

class TestEntityExtractor:
    extractor = EntityExtractor()

    def test_semester_extraction(self):
        assert self.extractor.extract("5th sem DBMS")["semester"] == 5
        assert self.extractor.extract("3rd semester physics")["semester"] == 3
        assert self.extractor.extract("semester 6 schedule")["semester"] == 6
        assert self.extractor.extract("first semester")["semester"] == 1

    def test_subject_extraction(self):
        result = self.extractor.extract("when is DBMS exam?")
        assert result["subject"] == "Database Management Systems"

    def test_branch_extraction(self):
        assert self.extractor.extract("CSE 5th sem")["branch"] == "CSE"
        assert self.extractor.extract("ECE schedule")["branch"] == "ECE"

    def test_no_entities_query(self):
        result = self.extractor.extract("hello world")
        assert result["semester"] is None
        assert result["subject"] is None
        assert result["branch"] is None

    def test_year_extraction(self):
        result = self.extractor.extract("2025-26 exam schedule")
        assert result["year"] is not None


# ── TextProcessor ─────────────────────────────────────────────────────────────

SAMPLE_CIRCULAR = """
Visvesvaraya Technological University
Belagavi

Circular No. VTU/AC/2025/123

All students are hereby informed that the 5th semester examination
for Computer Science and Engineering (CSE) will be held as follows:

CS501 - Data Structures and Algorithms  10/12/2025  10:30 AM
CS502 - Database Management Systems     12/12/2025  10:30 AM
CS503 - Operating Systems               14/12/2025  10:30 AM

The schedule is subject to change. Refer vtu.ac.in for updates.

Registrar
"""


class TestTextProcessor:
    processor = TextProcessor()

    def test_clean_removes_boilerplate(self):
        cleaned = self.processor.clean(SAMPLE_CIRCULAR)
        assert "Visvesvaraya" not in cleaned
        assert "Belagavi" not in cleaned
        assert "Registrar" not in cleaned

    def test_extract_exam_dates(self):
        dates = self.processor.extract_exam_dates(SAMPLE_CIRCULAR)
        assert len(dates) >= 3
        for entry in dates:
            assert "date_str" in entry
            assert "context" in entry

    def test_extract_semester_info(self):
        semesters = self.processor.extract_semester_info(SAMPLE_CIRCULAR)
        assert 5 in semesters

    def test_classify_exam_schedule(self):
        result = self.processor.process_circular(SAMPLE_CIRCULAR)
        assert result["circular_type"] == "EXAM_SCHEDULE"

    def test_empty_input(self):
        result = self.processor.process_circular("")
        assert result["cleaned_text"] == ""
        assert result["exam_dates"] == []

    def test_process_circular_keys(self):
        result = self.processor.process_circular(SAMPLE_CIRCULAR)
        for key in ["cleaned_text", "exam_dates", "subjects", "semesters", "circular_type"]:
            assert key in result
