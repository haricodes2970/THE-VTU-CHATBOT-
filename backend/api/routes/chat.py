"""
backend/api/routes/chat.py
Chat endpoints — POST /chat, GET /chat/history/{session_id}, DELETE /chat/session/{session_id}
"""
import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.chat_service import ChatService

router = APIRouter()
_chat_service = ChatService()

# Simple in-memory rate limiter: {session_id: [timestamps]}
_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 20          # requests per minute
RATE_WINDOW = 60.0       # seconds


def _check_rate_limit(session_id: str) -> None:
    now = time.time()
    window_start = now - RATE_WINDOW
    _rate_store[session_id] = [t for t in _rate_store[session_id] if t > window_start]
    if len(_rate_store[session_id]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {RATE_LIMIT} requests per minute per session.",
        )
    _rate_store[session_id].append(now)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500, description="User message")
    session_id: Optional[str] = Field(None, description="Session ID (omit to create new)")

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip()


class SourceItem(BaseModel):
    title: str = ""
    url: str = ""
    score: float = 0.0


class ChatResponseModel(BaseModel):
    answer: str
    intent: str
    entities: dict
    sources: list[SourceItem]
    session_id: str
    response_time_ms: int
    confidence: str


class HistoryMessage(BaseModel):
    role: str
    content: str
    timestamp: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/chat",
    response_model=ChatResponseModel,
    summary="Send a message to the VTU chatbot",
    description="Send a natural-language question and receive an AI-generated answer based on VTU circulars.",
)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Process a user message and return an AI response."""
    session_id = request.session_id or _chat_service.create_session()
    _check_rate_limit(session_id)

    response = _chat_service.chat(session_id, request.message, db=db)
    return ChatResponseModel(
        answer=response.answer,
        intent=response.intent,
        entities=response.entities,
        sources=[SourceItem(**s) for s in response.sources],
        session_id=response.session_id,
        response_time_ms=response.response_time_ms,
        confidence=response.confidence,
    )


@router.get(
    "/chat/history/{session_id}",
    response_model=HistoryResponse,
    summary="Get conversation history for a session",
)
async def get_history(session_id: str):
    """Return the last 10 messages for the given session."""
    messages = _chat_service.get_history(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryMessage(**m) for m in messages],
    )


@router.delete(
    "/chat/session/{session_id}",
    summary="Clear conversation history for a session",
)
async def clear_session(session_id: str):
    """Delete all messages in a session."""
    _chat_service.clear_history(session_id)
    return {"message": f"Session {session_id} cleared"}
