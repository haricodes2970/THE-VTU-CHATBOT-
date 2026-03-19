"""
tests/test_chat.py
Integration-style tests for the chat service (RAG mocked).
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.services.chat_service import ChatService


@pytest.fixture
def service():
    return ChatService()


@pytest.fixture
def session_id(service):
    return service.create_session()


class TestChatService:
    @patch("backend.services.chat_service._rag_chain")
    def test_chat_returns_answer(self, mock_chain, service, session_id):
        mock_chain.query.return_value = {
            "answer": "DBMS exam is on 10 December 2025 at 10:30 AM.",
            "intent": "GET_EXAM_DATE",
            "entities": {"subject": "Database Management Systems", "semester": 5},
            "sources": [],
            "retrieval_count": 3,
            "response_time_ms": 120,
        }
        response = service.chat(session_id, "When is my 5th sem DBMS exam?")
        assert response.answer
        assert "DBMS" in response.answer or "December" in response.answer
        assert response.confidence in ("HIGH", "MEDIUM", "LOW")

    @patch("backend.services.chat_service._rag_chain")
    def test_greeting_no_rag_call(self, mock_chain, service, session_id):
        response = service.chat(session_id, "Hello")
        mock_chain.query.assert_not_called()
        assert response.intent == "GREETING"
        assert response.confidence == "HIGH"

    @patch("backend.services.chat_service._rag_chain")
    def test_low_confidence_adds_disclaimer(self, mock_chain, service, session_id):
        mock_chain.query.return_value = {
            "answer": "I don't have that information.",
            "intent": "GENERAL_QUERY",
            "entities": {},
            "sources": [],
            "retrieval_count": 0,
            "response_time_ms": 50,
        }
        response = service.chat(session_id, "xyz garbage input")
        assert response.confidence == "LOW"
        assert "vtu.ac.in" in response.answer.lower()

    def test_get_history_returns_list(self, service, session_id):
        history = service.get_history(session_id)
        assert isinstance(history, list)

    @patch("backend.services.chat_service._rag_chain")
    def test_history_grows_with_messages(self, mock_chain, service, session_id):
        mock_chain.query.return_value = {
            "answer": "The schedule is available on VTU website.",
            "intent": "GET_EXAM_SCHEDULE",
            "entities": {"semester": 3},
            "sources": [],
            "retrieval_count": 2,
            "response_time_ms": 100,
        }
        service.chat(session_id, "Show me all exams for 3rd semester")
        history = service.get_history(session_id)
        assert len(history) >= 2  # user + assistant

    def test_clear_history(self, service, session_id):
        service.clear_history(session_id)
        history = service.get_history(session_id)
        assert history == []

    def test_create_session_returns_string(self, service):
        sid = service.create_session()
        assert isinstance(sid, str)
        assert len(sid) == 36  # UUID format
