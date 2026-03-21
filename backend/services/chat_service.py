"""
backend/services/chat_service.py
Chatbot orchestrator — ties RAG chain + conversation history into a single service.
Entity context (semester, scheme, course_type) persists across messages per session.
"""
import time
import uuid
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from backend.rag_pipeline.retriever import ContextRetriever
from backend.rag_pipeline.generator import ResponseGenerator
from backend.services.conversation_manager import ConversationManager
from ai.query_processing.intent_detector import Intent

# Singleton shared instances
_retriever = ContextRetriever()
_generator = ResponseGenerator()
_conv_manager = ConversationManager()

CONFIDENCE_HIGH = 0.8
CONFIDENCE_MEDIUM = 0.5
LOW_CONFIDENCE_DISCLAIMER = (
    "\n\n⚠️ Please verify this information with the official VTU website: vtu.ac.in"
)

GREETINGS = {
    Intent.GREETING: (
        "Hello! I'm your VTU Exam Assistant 🎓 "
        "I can help you find exam dates, schedules, circulars, and more. "
        "What would you like to know?"
    )
}


@dataclass
class ChatResponse:
    answer: str
    intent: str
    entities: dict
    sources: list
    session_id: str
    response_time_ms: int
    confidence: str  # HIGH | MEDIUM | LOW


class ChatService:
    """Main chatbot service — processes messages and returns structured responses."""

    def create_session(self) -> str:
        """Generate and register a new UUID session."""
        session_id = str(uuid.uuid4())
        _conv_manager.get_or_create(session_id)
        logger.info(f"New session created: {session_id}")
        return session_id

    def chat(self, session_id: str, message: str, db=None) -> ChatResponse:
        """Process a user message and return a ChatResponse."""
        t0 = time.perf_counter()

        _conv_manager.add_message(session_id, "user", message)

        # Handle greetings without hitting RAG
        from ai.query_processing.intent_detector import IntentDetector
        intent_result = IntentDetector().detect(message)
        if intent_result["intent"] == Intent.GREETING:
            answer = GREETINGS[Intent.GREETING]
            _conv_manager.add_message(session_id, "assistant", answer)
            elapsed = int((time.perf_counter() - t0) * 1000)
            return ChatResponse(
                answer=answer,
                intent=Intent.GREETING,
                entities={},
                sources=[],
                session_id=session_id,
                response_time_ms=elapsed,
                confidence="HIGH",
            )

        # Process query to extract intent + entities + search query
        from ai.query_processing.query_processor import QueryProcessor
        processed = QueryProcessor().process(message)
        intent = processed.get("intent", "GENERAL_QUERY")
        entities = processed.get("entities", {})
        search_query = processed.get("search_query", message)

        # Merge new entities into session (persists semester/scheme across messages)
        _conv_manager.update_entities(session_id, entities)
        session_entities = _conv_manager.get_entities(session_id)

        # Pull usable filters from accumulated session context
        scheme = session_entities.get("scheme")
        semester = session_entities.get("semester")
        course_type = session_entities.get("course_type")

        # Retrieve context — use targeted method for exam queries
        if scheme or semester or course_type:
            chunks = _retriever.retrieve_for_exam_query(
                search_query,
                scheme=scheme,
                semester=str(semester) if semester else None,
                course_type=course_type,
                top_k=5,
            )
        else:
            chunks = _retriever.retrieve(search_query, top_k=5)

        # Pre-fetch fallback PDF URL (only if needed; cheap DB call)
        fallback_pdf_url: Optional[str] = None
        if db is not None and (scheme or course_type):
            fallback_pdf_url = _retriever.get_latest_timetable_pdf_url(
                scheme=scheme, course_type=course_type, db=db
            )

        # Generate answer (with structured fallback logic)
        answer = _generator.generate_with_fallback(
            query=message,
            context_chunks=chunks,
            fallback_pdf_url=fallback_pdf_url,
            session_id=session_id,
            session_entities=session_entities,
            db=db,
        )

        # Compute confidence
        retrieval_count = len(chunks)
        if retrieval_count == 0:
            confidence = "LOW"
        elif retrieval_count >= 3:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        if confidence == "LOW" and answer not in (
            "NOT_FOUND",
        ) and "Could you tell me" not in answer:
            answer += LOW_CONFIDENCE_DISCLAIMER

        _conv_manager.add_message(session_id, "assistant", answer)
        elapsed = int((time.perf_counter() - t0) * 1000)

        # Build sources from chunks
        sources = [
            {
                "title": c.get("metadata", {}).get("title", ""),
                "url": c.get("metadata", {}).get("pdf_url", "")
                or c.get("metadata", {}).get("source_url", ""),
                "score": c.get("score", 0),
            }
            for c in chunks
        ]

        return ChatResponse(
            answer=answer,
            intent=intent,
            entities=session_entities,
            sources=sources,
            session_id=session_id,
            response_time_ms=elapsed,
            confidence=confidence,
        )

    def get_history(self, session_id: str) -> list[dict]:
        """Return last 10 messages for a session."""
        return _conv_manager.get_history(session_id)[-10:]

    def clear_history(self, session_id: str) -> None:
        """Clear session conversation history."""
        _conv_manager.clear_session(session_id)
        logger.info(f"Session cleared: {session_id}")
