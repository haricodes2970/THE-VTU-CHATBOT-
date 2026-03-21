"""
backend/services/conversation_manager.py
In-memory conversation history manager with TTL-based expiry.
"""
import uuid
from datetime import datetime, timedelta
from threading import Lock
from typing import Optional

from loguru import logger

SESSION_TTL_HOURS = 2
MAX_CONTEXT_EXCHANGES = 5


class ConversationManager:
    """
    Thread-safe in-memory store for conversation history.
    Sessions expire after SESSION_TTL_HOURS of inactivity.
    """

    def __init__(self):
        self._sessions: dict[str, dict] = {}
        self._lock = Lock()

    def _new_session(self, session_id: str) -> dict:
        return {
            "messages": [],
            "created_at": datetime.utcnow(),
            "last_active": datetime.utcnow(),
            "message_count": 0,
            # Extracted entities persist across messages in the same session
            "entities": {},
        }

    def get_or_create(self, session_id: str) -> dict:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = self._new_session(session_id)
            return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Append a message to the session history."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = self._new_session(session_id)
            session = self._sessions[session_id]
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.utcnow().isoformat(),
            })
            session["message_count"] += 1
            session["last_active"] = datetime.utcnow()

    def get_context(self, session_id: str) -> list[dict]:
        """Return last MAX_CONTEXT_EXCHANGES exchanges formatted for the LLM."""
        session = self.get_or_create(session_id)
        messages = session["messages"]
        # Keep last N exchanges (each exchange = 2 messages: user + assistant)
        cutoff = MAX_CONTEXT_EXCHANGES * 2
        return messages[-cutoff:] if len(messages) > cutoff else messages[:]

    def get_history(self, session_id: str) -> list[dict]:
        """Return full history for a session."""
        session = self.get_or_create(session_id)
        return session["messages"][:]

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def cleanup_expired(self) -> int:
        """Remove sessions that haven't been active for SESSION_TTL_HOURS. Returns count removed."""
        cutoff = datetime.utcnow() - timedelta(hours=SESSION_TTL_HOURS)
        with self._lock:
            expired = [
                sid for sid, sess in self._sessions.items()
                if sess["last_active"] < cutoff
            ]
            for sid in expired:
                del self._sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)

    def update_entities(self, session_id: str, new_entities: dict) -> None:
        """
        Merge new_entities into the session's persisted entity dict.
        Only non-empty values overwrite existing ones.
        """
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = self._new_session(session_id)
            existing = self._sessions[session_id].setdefault("entities", {})
            for k, v in new_entities.items():
                if v:
                    existing[k] = v

    def get_entities(self, session_id: str) -> dict:
        """Return persisted entities for a session."""
        session = self.get_or_create(session_id)
        return dict(session.get("entities", {}))

    def get_stats(self) -> dict:
        """Return active session count and message stats."""
        with self._lock:
            today = datetime.utcnow().date()
            total_today = sum(
                sum(
                    1 for m in sess["messages"]
                    if m["timestamp"].startswith(today.isoformat())
                )
                for sess in self._sessions.values()
            )
            return {
                "active_sessions": len(self._sessions),
                "total_messages_today": total_today,
            }
