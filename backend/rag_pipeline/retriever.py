"""
backend/rag_pipeline/retriever.py
Retrieves relevant document chunks from Pinecone based on a query embedding.
"""
import time
from typing import Optional

from loguru import logger

from ai.embeddings.embedding_generator import EmbeddingGenerator
from backend.core.config import settings

MIN_SCORE = 0.5


class ContextRetriever:
    """Queries Pinecone to find the most relevant text chunks for a user query."""

    def __init__(self):
        self._generator = EmbeddingGenerator()
        self._index = None

    @property
    def index(self):
        if self._index is None:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.pinecone_api_key)
            self._index = pc.Index(settings.pinecone_index_name)
        return self._index

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve top_k most relevant chunks for query.
        Returns list of {text, score, metadata}.
        """
        t0 = time.perf_counter()
        try:
            embedding = self._generator.generate_query_embedding(query)
            response = self.index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
            )
            results = [
                {
                    "text": match.metadata.get("text", ""),
                    "score": round(match.score, 4),
                    "metadata": dict(match.metadata),
                }
                for match in response.matches
                if match.score >= MIN_SCORE
            ]
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                f"Retrieved {len(results)}/{top_k} chunks in {elapsed:.1f}ms "
                f"(query='{query[:60]}')"
            )
            return results
        except Exception as e:
            logger.error(f"Pinecone retrieval error: {e}")
            return []

    def retrieve_with_filters(
        self, query: str, filters: dict, top_k: int = 5
    ) -> list[dict]:
        """
        Retrieve with Pinecone metadata filters.
        Supported filters: semester, subject.
        """
        t0 = time.perf_counter()
        try:
            embedding = self._generator.generate_query_embedding(query)

            # Build Pinecone filter expression
            pinecone_filter: dict = {}
            if "semester" in filters:
                pinecone_filter["semester"] = {"$eq": str(filters["semester"])}
            if "subject" in filters:
                pinecone_filter["title"] = {"$eq": str(filters["subject"])}

            kwargs = {"vector": embedding, "top_k": top_k, "include_metadata": True}
            if pinecone_filter:
                kwargs["filter"] = pinecone_filter

            response = self.index.query(**kwargs)
            results = [
                {
                    "text": match.metadata.get("text", ""),
                    "score": round(match.score, 4),
                    "metadata": dict(match.metadata),
                }
                for match in response.matches
                if match.score >= MIN_SCORE
            ]
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                f"Filtered retrieval: {len(results)} results in {elapsed:.1f}ms"
            )
            return results
        except Exception as e:
            logger.error(f"Filtered retrieval error: {e}")
            return []

    def retrieve_exam_date(
        self, subject: str, semester: Optional[int] = None
    ) -> Optional[dict]:
        """
        Specialised retrieval for exam date queries.
        Returns the single most relevant result or None.
        """
        query = f"{subject} exam date"
        if semester:
            query += f" {semester}th semester"

        filters = {}
        if semester:
            filters["semester"] = semester

        results = self.retrieve_with_filters(query, filters, top_k=3)
        if results:
            return results[0]
        # Fallback without filters
        fallback = self.retrieve(query, top_k=1)
        return fallback[0] if fallback else None
