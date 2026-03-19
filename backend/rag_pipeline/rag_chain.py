"""
backend/rag_pipeline/rag_chain.py
Orchestrates the full RAG pipeline: query → retrieve → generate → respond.
"""
import time
from typing import Optional

from loguru import logger

from ai.query_processing.query_processor import QueryProcessor
from backend.rag_pipeline.retriever import ContextRetriever
from backend.rag_pipeline.generator import ResponseGenerator
from backend.rag_pipeline.embedder import VectorEmbedder

NO_INFO_RESPONSE = (
    "I don't have information about that in my knowledge base. "
    "Please check the official VTU website at vtu.ac.in for the latest details."
)


class RAGChain:
    """End-to-end RAG pipeline: process query → retrieve context → generate answer."""

    def __init__(self):
        self._query_processor = QueryProcessor()
        self._retriever = ContextRetriever()
        self._generator = ResponseGenerator()
        self._embedder = VectorEmbedder()
        # Simple in-memory conversation history per session
        self._history: dict[str, list[dict]] = {}

    def query(self, user_query: str, session_id: Optional[str] = None) -> dict:
        """
        Full end-to-end query.
        Returns: {answer, sources, intent, entities, retrieval_count, response_time_ms}
        """
        t0 = time.perf_counter()
        logger.info(f"RAG query: '{user_query[:80]}'")

        # 1. Process query
        processed = self._query_processor.process(user_query)
        intent = processed["intent"]
        entities = processed["entities"]
        search_query = processed["search_query"]
        filters = processed["filters"]

        # 2. Retrieve context
        if filters:
            chunks = self._retriever.retrieve_with_filters(search_query, filters, top_k=5)
        else:
            chunks = self._retriever.retrieve(search_query, top_k=5)

        # 3. No relevant context
        if not chunks:
            logger.warning(f"No relevant chunks found for: '{user_query[:60]}'")
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "answer": NO_INFO_RESPONSE,
                "sources": [],
                "intent": intent,
                "entities": entities,
                "retrieval_count": 0,
                "response_time_ms": round(elapsed),
            }

        # 4. Generate response
        result = self._generator.generate_with_citations(user_query, chunks)
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            f"RAG complete: intent={intent}, chunks={len(chunks)}, "
            f"time={elapsed:.0f}ms"
        )
        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "intent": intent,
            "entities": entities,
            "retrieval_count": len(chunks),
            "response_time_ms": round(elapsed),
        }

    def index_circular(self, circular, db=None) -> int:
        """Chunks and embeds a single Circular model instance."""
        return self._embedder.embed_circular(circular, db=db)

    def index_all_pending(self, db) -> dict:
        """
        Embeds all circulars in DB that are not yet indexed.
        Returns summary {total, indexed, failed}.
        """
        from backend.services.circular_service import CircularService
        pending = CircularService().get_unprocessed(db)
        logger.info(f"Indexing {len(pending)} pending circulars")

        indexed, failed = 0, 0
        for circular in pending:
            try:
                count = self.index_circular(circular, db=db)
                if count > 0:
                    indexed += 1
            except Exception as e:
                logger.error(f"Failed to index circular {circular.id}: {e}")
                failed += 1

        return {"total": len(pending), "indexed": indexed, "failed": failed}
