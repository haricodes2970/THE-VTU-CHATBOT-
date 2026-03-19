"""
ai/query_processing/query_processor.py
Combines intent detection and entity extraction into a single processed query object.
"""
from loguru import logger

from ai.query_processing.intent_detector import IntentDetector, Intent
from ai.query_processing.entity_extractor import EntityExtractor


class QueryProcessor:
    """Processes raw user queries into structured objects for the RAG pipeline."""

    def __init__(self):
        self._intent_detector = IntentDetector()
        self._entity_extractor = EntityExtractor()

    def process(self, query: str) -> dict:
        """
        Full query processing.
        Returns:
        {
            original_query, intent, entities,
            search_query, filters
        }
        """
        intent_result = self._intent_detector.detect(query)
        entities = self._entity_extractor.extract(query)

        search_query = self.build_search_query(intent_result["intent"], entities, query)
        filters = self._build_filters(entities)

        result = {
            "original_query": query,
            "intent": intent_result["intent"],
            "intent_confidence": intent_result["confidence"],
            "entities": entities,
            "search_query": search_query,
            "filters": filters,
        }
        logger.debug(f"Processed query: {result}")
        return result

    def build_search_query(self, intent: str, entities: dict, original: str = "") -> str:
        """
        Build a clean, optimised query string for vector search.
        Example: "when is 5th sem DBMS exam"
                 → "DBMS exam date 5th semester"
        """
        parts: list[str] = []

        if entities.get("subject"):
            parts.append(entities["subject"])

        if intent == Intent.GET_EXAM_DATE:
            parts.append("exam date")
        elif intent == Intent.GET_EXAM_SCHEDULE:
            parts.append("exam schedule timetable")
        elif intent == Intent.GET_CIRCULAR:
            parts.append("circular notification")
        elif intent == Intent.GET_RESULTS:
            parts.append("results marks")

        if entities.get("semester"):
            parts.append(f"{entities['semester']}th semester")
        if entities.get("branch"):
            parts.append(entities["branch"])
        if entities.get("year"):
            parts.append(entities["year"])

        if not parts:
            return original  # Fall back to original query if nothing extracted

        return " ".join(parts)

    def _build_filters(self, entities: dict) -> dict:
        """Build database filter dict from extracted entities."""
        filters: dict = {}
        if entities.get("semester"):
            filters["semester"] = entities["semester"]
        if entities.get("branch"):
            filters["branch"] = entities["branch"]
        if entities.get("subject"):
            filters["subject"] = entities["subject"]
        return filters
