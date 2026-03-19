"""
ai/query_processing/entity_extractor.py
Extracts structured entities (semester, subject, branch, year, date) from user queries.
"""
import re
from typing import Optional

from loguru import logger

try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    _nlp = None
    SPACY_AVAILABLE = False

# ── Subject aliases ───────────────────────────────────────────────────────────
SUBJECT_ALIASES: dict[str, str] = {
    "DS": "Data Structures",
    "ADA": "Analysis and Design of Algorithms",
    "DBMS": "Database Management Systems",
    "OS": "Operating Systems",
    "CN": "Computer Networks",
    "SE": "Software Engineering",
    "CD": "Compiler Design",
    "TOC": "Theory of Computation",
    "AI": "Artificial Intelligence",
    "ML": "Machine Learning",
    "DL": "Deep Learning",
    "CC": "Cloud Computing",
    "IS": "Information Security",
    "FLAT": "Formal Languages and Automata Theory",
    "OOP": "Object Oriented Programming",
    "JAVA": "Java Programming",
    "PYTHON": "Python Programming",
    "WEB": "Web Technologies",
    "DM": "Discrete Mathematics",
    "M1": "Engineering Mathematics 1",
    "M2": "Engineering Mathematics 2",
    "M3": "Engineering Mathematics 3",
    "M4": "Engineering Mathematics 4",
    "PHY": "Engineering Physics",
    "CHEM": "Engineering Chemistry",
    "EVS": "Environmental Science",
    "EG": "Engineering Graphics",
    "BE": "Business Economics",
    "MATHS": "Mathematics",
    "DATA STRUCT": "Data Structures",
    "ALGO": "Analysis and Design of Algorithms",
    "NETWORKS": "Computer Networks",
    "COMPILERS": "Compiler Design",
}

# ── Branch aliases ────────────────────────────────────────────────────────────
BRANCH_ALIASES: dict[str, str] = {
    "CS": "CSE", "COMPUTER": "CSE", "COMPUTER SCIENCE": "CSE",
    "EC": "ECE", "ELECTRONICS": "ECE", "ELECTRONICS AND COMMUNICATION": "ECE",
    "IS": "ISE", "INFORMATION": "ISE", "INFO SCI": "ISE",
    "ME": "MECH", "MECHANICAL": "MECH",
    "CV": "CIVIL", "CIVIL ENGINEERING": "CIVIL",
    "EE": "EEE", "ELECTRICAL": "EEE",
    "BT": "BIOTECH", "BIOTECHNOLOGY": "BIOTECH",
    "CH": "CHEM", "CHEMICAL": "CHEM",
}

# ── Semester patterns ─────────────────────────────────────────────────────────
_SEM_PATTERNS = [
    (r"\b(\d)[stndrh]{0,2}\s*sem(?:ester)?\b", lambda m: int(m.group(1))),
    (r"\bsem(?:ester)?\s*(\d)\b", lambda m: int(m.group(1))),
    (r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth)\s+sem", None),
]
_ORDINAL_MAP = {
    "first": 1, "second": 2, "third": 3, "fourth": 4,
    "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
}


class EntityExtractor:
    """Extracts structured entities from natural language queries."""

    def _extract_semester(self, query: str) -> Optional[int]:
        q = query.lower()
        for pattern, extractor in _SEM_PATTERNS:
            m = re.search(pattern, q)
            if m:
                if extractor:
                    return extractor(m)
                else:
                    word = m.group(1)
                    return _ORDINAL_MAP.get(word)
        return None

    def _extract_subject(self, query: str) -> Optional[str]:
        q_upper = query.upper()
        # Exact alias match first
        for alias, full_name in SUBJECT_ALIASES.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", q_upper):
                return full_name
        # Partial match (case-insensitive substring)
        q_lower = query.lower()
        for alias, full_name in SUBJECT_ALIASES.items():
            if alias.lower() in q_lower or full_name.lower() in q_lower:
                return full_name
        # spaCy PROPN fallback
        if SPACY_AVAILABLE and _nlp is not None:
            doc = _nlp(query)
            for ent in doc.ents:
                if ent.label_ in ("ORG", "PRODUCT", "WORK_OF_ART"):
                    return ent.text
        return None

    def _extract_branch(self, query: str) -> Optional[str]:
        q_upper = query.upper()
        for alias, norm in BRANCH_ALIASES.items():
            if re.search(r"\b" + re.escape(alias) + r"\b", q_upper):
                return norm
        # Known canonical names
        for branch in ["CSE", "ECE", "ISE", "MECH", "CIVIL", "EEE", "BIOTECH"]:
            if re.search(r"\b" + branch + r"\b", q_upper):
                return branch
        return None

    def _extract_year(self, query: str) -> Optional[str]:
        m = re.search(r"\b(20\d{2}[-–]\d{2,4})\b", query)
        if m:
            return m.group(1)
        m = re.search(r"\b(first|second|third|fourth)\s+year\b", query, re.IGNORECASE)
        if m:
            return m.group(0).lower()
        return None

    def _extract_date(self, query: str) -> Optional[str]:
        m = re.search(
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", query
        )
        return m.group(1) if m else None

    def extract(self, query: str) -> dict:
        """
        Extract all entities from a query.
        Returns: {semester, subject, branch, year, date}
        """
        return {
            "semester": self._extract_semester(query),
            "subject": self._extract_subject(query),
            "branch": self._extract_branch(query),
            "year": self._extract_year(query),
            "date": self._extract_date(query),
        }
