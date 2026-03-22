"""Unit tests for VTU metadata extraction functions."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from scraper.vtu_scraper import VTUScraper


@pytest.fixture
def scraper():
    return VTUScraper.__new__(VTUScraper)


class TestDetectScheme:
    def test_2022_scheme_parentheses(self, scraper):
        assert scraper.detect_scheme("Time Table for B.E/B.Tech. (2022 Scheme) VI Semester") == "2022"

    def test_2021_scheme_plain(self, scraper):
        assert scraper.detect_scheme("Time Table for 2021 Scheme, III/IV Semester") == "2021"

    def test_2021_scheme_parentheses(self, scraper):
        assert scraper.detect_scheme("Revised Time Table for I/II Semester (2021 Scheme)") == "2021"

    def test_2022_scheme_no_parens(self, scraper):
        assert scraper.detect_scheme("III Semester 2022 Scheme BE/BTech Examination") == "2022"

    def test_filename_2021_be(self, scraper):
        assert scraper.detect_scheme("2021_BE_3_4SEM_JUN24") == "2021"

    def test_mtech_returns_pg(self, scraper):
        assert scraper.detect_scheme("Time Table for M.Tech. I Semester (2022 Scheme) Dec 2025") == "2022"

    def test_pgcism_returns_pg(self, scraper):
        assert scraper.detect_scheme("TT_PGCISM_JJ25") == "PG"

    def test_cbcs_returns_2018(self, scraper):
        assert scraper.detect_scheme("Time Table CBCS scheme examination") == "2018"

    def test_default_2021(self, scraper):
        assert scraper.detect_scheme("TimeTable_Dec25_Jan26_Phase_I") == "2021"

    def test_2022_scheme_dec_2025(self, scraper):
        assert scraper.detect_scheme("CIRCULAR – Time Table for B.E/B.Tech. (2022 Scheme) VI Semester Examination Dec 2025/Jan 2026") == "2022"


class TestExtractSemesterRange:
    def test_roman_pair_slash(self, scraper):
        assert scraper.extract_semester_range("Time Table for 2021 Scheme, III/IV Semester") == "3/4"

    def test_roman_pair_slash_lower(self, scraper):
        assert scraper.extract_semester_range("I/II Semester (2021 Scheme)") == "1/2"

    def test_roman_and(self, scraper):
        assert scraper.extract_semester_range("Draft Time Table for I and II Semester (2022 Scheme)") == "1/2"

    def test_single_roman_vi(self, scraper):
        assert scraper.extract_semester_range("(2022 Scheme) VI Semester Examination Dec 2025") == "6"

    def test_single_roman_i(self, scraper):
        assert scraper.extract_semester_range("M.Tech. I Semester (2022 Scheme)") == "1"

    def test_single_roman_iii(self, scraper):
        assert scraper.extract_semester_range("Revised Time Table for III Semester 2022 Scheme") == "3"

    def test_ordinal_5th(self, scraper):
        assert scraper.extract_semester_range("Time Table for 5th Semester B.E./B.Tech. (2021 Scheme)") == "5"

    def test_underscore_3_4(self, scraper):
        assert scraper.extract_semester_range("2021_BE_3_4SEM_JUN24") == "3/4"

    def test_default_all(self, scraper):
        assert scraper.extract_semester_range("TimeTable_Dec25_Jan26_Phase_I") == "all"

    def test_v_vi_pair(self, scraper):
        assert scraper.extract_semester_range("V/VI Semester exam") == "5/6"


class TestExtractExamSession:
    def test_dec_jan_slash(self, scraper):
        assert scraper.extract_exam_session("(2022 Scheme) VI Semester Examination Dec 2025/Jan 2026") == "Dec2025"

    def test_june_july_slash(self, scraper):
        assert scraper.extract_exam_session("2021 Scheme, III/IV Semester, June/July 2024") == "Jun2024"

    def test_jan_feb(self, scraper):
        assert scraper.extract_exam_session("I/II Semester (2021 Scheme) Jan/Feb 2023") == "Jan2023"

    def test_nov_dec(self, scraper):
        assert scraper.extract_exam_session("5th Semester B.E./B.Tech. (2021 Scheme) Nov/Dec 2023") == "Nov2023"

    def test_dec_2025_full(self, scraper):
        assert scraper.extract_exam_session("M.Tech. I Semester (2022 Scheme) Examination Dec 2025") == "Dec2025"

    def test_filename_jj25(self, scraper):
        assert scraper.extract_exam_session("TT_PGCISM_JJ25") == "Jun2025"

    def test_filename_dec25_jan26(self, scraper):
        assert scraper.extract_exam_session("TimeTable_Dec25_Jan26_Phase_I") == "Dec2025"

    def test_filename_2021be_jun2024(self, scraper):
        assert scraper.extract_exam_session("TimeTable_2021BE_Jun2024") == "Jun2024"

    def test_filename_jun24_underscore(self, scraper):
        assert scraper.extract_exam_session("2021_BE_3_4SEM_JUN24") == "Jun2024"

    def test_dec_2024_jan_2025(self, scraper):
        assert scraper.extract_exam_session("Draft Time Table for I and II Semester (2022 Scheme) B.E./B.Tech. Dec 2024/Jan 2025") == "Dec2024"

    def test_unknown_fallback(self, scraper):
        assert scraper.extract_exam_session("Revised Time Table for III Semester 2022 Scheme BE/BTech Examination") == "UnknownSession"
