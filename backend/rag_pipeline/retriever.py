"""
backend/rag_pipeline/retriever.py
Retrieves relevant document chunks from Pinecone based on a query embedding.

All queries include is_latest=True filter so superseded timetables are
never surfaced to users, even if old vectors linger in the index.
"""
import time
from typing import Optional

from loguru import logger

from ai.embeddings.embedding_generator import EmbeddingGenerator
from backend.core.config import settings

MIN_SCORE = 0.2


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

    # ── Core retrieval ────────────────────────────────────────────

    def _query_pinecone(
        self, embedding: list[float], top_k: int, extra_filter: dict | None = None
    ) -> list[dict]:
        """
        Run a Pinecone query with is_latest=True always applied.
        Merges extra_filter on top.
        Returns filtered list of {text, score, metadata}.
        """
        pinecone_filter: dict = {"is_latest": {"$eq": True}}
        if extra_filter:
            pinecone_filter.update(extra_filter)

        response = self.index.query(
            vector=embedding,
            top_k=top_k,
            include_metadata=True,
            filter=pinecone_filter,
        )
        return [
            {
                "text": match.metadata.get("text", ""),
                "score": round(match.score, 4),
                "metadata": dict(match.metadata),
            }
            for match in response.matches
            if match.score >= MIN_SCORE
        ]

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve top_k most relevant chunks for query (is_latest=True filter applied).
        Returns list of {text, score, metadata}.
        """
        t0 = time.perf_counter()
        try:
            embedding = self._generator.generate_query_embedding(query)
            results = self._query_pinecone(embedding, top_k)
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
        Retrieve with additional Pinecone metadata filters on top of is_latest=True.
        Legacy method — prefer retrieve_for_exam_query for timetable queries.
        """
        t0 = time.perf_counter()
        try:
            embedding = self._generator.generate_query_embedding(query)
            extra: dict = {}
            if "semester" in filters:
                extra["semester_range"] = {"$eq": str(filters["semester"])}

            results = self._query_pinecone(embedding, top_k, extra_filter=extra)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                f"Filtered retrieval: {len(results)} results in {elapsed:.1f}ms"
            )
            return results
        except Exception as e:
            logger.error(f"Filtered retrieval error: {e}")
            return []

    def retrieve_for_exam_query(
        self,
        query: str,
        scheme: str | None = None,
        semester: str | None = None,
        course_type: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Targeted retrieval for exam date / timetable questions.
        Builds Pinecone filter from known user context (scheme, semester, course_type).
        Always includes is_latest=True.
        Falls back to unfiltered retrieval if no context provided.
        """
        t0 = time.perf_counter()
        try:
            embedding = self._generator.generate_query_embedding(query)
            extra: dict = {}

            if scheme:
                extra["scheme"] = {"$eq": scheme}
            if course_type:
                extra["course_type"] = {"$eq": course_type}
            if semester:
                # semester_range can be "3/4", "5/6", "7/8", "3", "5", "all"
                # Build an $in list covering both the pair and individual values
                possible = {semester}
                # If "3" is provided, also match "3/4"
                for pair in ["1/2", "3/4", "5/6", "7/8"]:
                    if semester in pair.split("/"):
                        possible.add(pair)
                extra["semester_range"] = {"$in": list(possible)}

            results = self._query_pinecone(embedding, top_k, extra_filter=extra or None)

            # If filtered yields nothing, retry without filters (broader search)
            if not results and extra:
                logger.info(
                    "retrieve_for_exam_query: no filtered results, retrying without filters"
                )
                results = self._query_pinecone(embedding, top_k, extra_filter=None)

            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                f"Exam query retrieval: {len(results)} results in {elapsed:.1f}ms "
                f"(scheme={scheme}, sem={semester}, course={course_type})"
            )
            return results
        except Exception as e:
            logger.error(f"retrieve_for_exam_query error: {e}")
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

        results = self.retrieve_for_exam_query(
            query,
            semester=str(semester) if semester else None,
            top_k=3,
        )
        return results[0] if results else None

    # ── DB fallback helper ─────────────────────────────────────────

    def get_latest_timetable_pdf_url(
        self,
        scheme: str | None = None,
        course_type: str | None = None,
        db=None,
    ) -> str | None:
        """
        Query PostgreSQL for the most recently published non-superseded circular
        matching scheme + course_type. Returns PDF URL for last-resort fallback.
        """
        if db is None:
            return None
        try:
            from backend.services.circular_service import CircularService
            return CircularService().get_latest_timetable_pdf_url(
                db, scheme=scheme, course_type=course_type
            )
        except Exception as e:
            logger.error(f"get_latest_timetable_pdf_url error: {e}")
            return None
