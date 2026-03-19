"""
backend/services/nlp_service.py
FastAPI-friendly wrapper around QueryProcessor. spaCy model loaded once on startup.
"""
from functools import lru_cache

from loguru import logger

from ai.query_processing.query_processor import QueryProcessor


@lru_cache(maxsize=1)
def _get_processor() -> QueryProcessor:
    """Singleton QueryProcessor — spaCy model loaded once."""
    logger.info("Loading NLP QueryProcessor (spaCy model)")
    return QueryProcessor()


class NLPService:
    """Thin service wrapper for use in FastAPI route handlers."""

    def process_query(self, text: str) -> dict:
        """Process a user query and return structured result."""
        processor = _get_processor()
        return processor.process(text)
