"""
ai/query_processing/intent_detector.py
Detects user intent from natural language queries using rule-based + spaCy approach.
"""
import re
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

# Load spaCy model once at module level
try:
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    SPACY_AVAILABLE = True
except Exception:
    _nlp = None
    SPACY_AVAILABLE = False
    logger.warning("spaCy model not loaded — intent detection will use rule-based only")


class Intent:
    GET_EXAM_DATE = "GET_EXAM_DATE"
    GET_EXAM_SCHEDULE = "GET_EXAM_SCHEDULE"
    GET_CIRCULAR = "GET_CIRCULAR"
    GET_RESULTS = "GET_RESULTS"
    GENERAL_QUERY = "GENERAL_QUERY"
    GREETING = "GREETING"


# Keyword patterns for each intent
_INTENT_PATTERNS: dict[str, list[str]] = {
    Intent.GET_EXAM_DATE: [
        r"\bwhen\b.*\bexam\b",
        r"\bdate\b.*\bexam\b",
        r"\bexam\b.*\bdate\b",
        r"\bexam\b.*\bwhen\b",
        r"\bschedule\b.*\bdate\b",
    ],
    Intent.GET_EXAM_SCHEDULE: [
        r"\bschedule\b",
        r"\btimetable\b",
        r"\btime.?table\b",
        r"\ball exams?\b",
        r"\bshow.*exams?\b",
        r"\blist.*exams?\b",
    ],
    Intent.GET_CIRCULAR: [
        r"\bcircular\b",
        r"\bnotif",
        r"\bannouncement\b",
        r"\bnotice\b",
        r"\blatest\b.*\bcircular\b",
        r"\bnew\b.*\bcircular\b",
        r"\bupdate\b",
    ],
    Intent.GET_RESULTS: [
        r"\bresult\b",
        r"\bmarks?\b",
        r"\bscore\b",
        r"\bcia\b",
        r"\bcie\b",
        r"\bsee?e\b",
    ],
    Intent.GREETING: [
        r"^\s*(hi|hello|hey|good\s+(morning|afternoon|evening)|howdy)\s*[!?.]*\s*$",
    ],
}

# Abbreviation normalisations applied before intent detection
_ABBREV = {
    r"\bsem\b": "semester",
    r"\bsub\b": "subject",
    r"\bdept\b": "department",
    r"\btt\b": "timetable",
    r"\btt\b": "timetable",
    r"\bsch\b": "schedule",
}


class IntentDetector:
    """Detects intent from a user query string."""

    def _normalise(self, query: str) -> str:
        q = query.lower().strip()
        for abbrev, expansion in _ABBREV.items():
            q = re.sub(abbrev, expansion, q, flags=re.IGNORECASE)
        return q

    def detect(self, query: str) -> dict:
        """
        Detect intent from query.
        Returns: {intent: str, confidence: float, raw_query: str}
        """
        normalised = self._normalise(query)
        scores: dict[str, float] = {}

        for intent, patterns in _INTENT_PATTERNS.items():
            hit_count = sum(
                1 for p in patterns if re.search(p, normalised, re.IGNORECASE)
            )
            if hit_count:
                scores[intent] = hit_count / len(patterns)

        # Boost using spaCy verb/noun POS tags
        if SPACY_AVAILABLE and _nlp is not None:
            doc = _nlp(normalised)
            verbs = {t.lemma_ for t in doc if t.pos_ == "VERB"}
            nouns = {t.lemma_ for t in doc if t.pos_ in ("NOUN", "PROPN")}

            if "show" in verbs or "list" in verbs or "give" in verbs:
                scores[Intent.GET_EXAM_SCHEDULE] = (
                    scores.get(Intent.GET_EXAM_SCHEDULE, 0) + 0.2
                )
            if "date" in nouns or "when" in {t.lemma_ for t in doc}:
                scores[Intent.GET_EXAM_DATE] = (
                    scores.get(Intent.GET_EXAM_DATE, 0) + 0.2
                )

        if not scores:
            return {
                "intent": Intent.GENERAL_QUERY,
                "confidence": 0.3,
                "raw_query": query,
            }

        best_intent = max(scores, key=lambda k: scores[k])
        confidence = min(scores[best_intent] + 0.4, 1.0)

        return {
            "intent": best_intent,
            "confidence": round(confidence, 2),
            "raw_query": query,
        }
