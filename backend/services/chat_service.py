"""
backend/services/chat_service.py
Chatbot orchestrator — ties RAG chain + conversation history into a single service.
"""
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from loguru import logger

from backend.rag_pipeline.rag_chain import RAGChain
from backend.services.conversation_manager import ConversationManager
from ai.query_processing.intent_detector import Intent

# Singleton shared instances
_rag_chain = RAGChain()
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

    def chat(self, session_id: str, message: str) -> ChatResponse:
        """Process a user message and return a ChatResponse."""
        t0 = time.perf_counter()

        # Record user message
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

        # RAG query
        rag_result = _rag_chain.query(message, session_id=session_id)

        # Compute confidence
        retrieval_count = rag_result.get("retrieval_count", 0)
        if retrieval_count == 0:
            confidence = "LOW"
        elif retrieval_count >= 3:
            confidence = "HIGH"
        else:
            confidence = "MEDIUM"

        answer = rag_result["answer"]
        if confidence == "LOW":
            answer += LOW_CONFIDENCE_DISCLAIMER

        _conv_manager.add_message(session_id, "assistant", answer)
        elapsed = int((time.perf_counter() - t0) * 1000)

        return ChatResponse(
            answer=answer,
            intent=rag_result.get("intent", "GENERAL_QUERY"),
            entities=rag_result.get("entities", {}),
            sources=rag_result.get("sources", []),
            session_id=session_id,
            response_time_ms=elapsed,
            confidence=confidence,
        )

    def get_history(self, session_id: str) -> list[dict]:
        """Return last 10 messages for a session."""
        history = _conv_manager.get_history(session_id)
        return history[-10:]

    def clear_history(self, session_id: str) -> None:
        """Clear session conversation history."""
        _conv_manager.clear_session(session_id)
        logger.info(f"Session cleared: {session_id}")
