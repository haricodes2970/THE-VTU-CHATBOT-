"""
tests/test_api.py
Integration tests for all FastAPI endpoints using httpx TestClient.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        with patch("backend.main.check_db_connection", return_value=True):
            resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "app" in data


# ── Chat ──────────────────────────────────────────────────────────────────────

class TestChatEndpoint:
    @patch("backend.api.routes.chat._chat_service")
    def test_post_chat_valid(self, mock_service):
        from backend.services.chat_service import ChatResponse
        mock_service.create_session.return_value = "test-session-id"
        mock_service.chat.return_value = ChatResponse(
            answer="DBMS exam is on 10 Dec 2025.",
            intent="GET_EXAM_DATE",
            entities={"subject": "DBMS"},
            sources=[],
            session_id="test-session-id",
            response_time_ms=100,
            confidence="HIGH",
        )
        resp = client.post("/api/v1/chat", json={"message": "When is DBMS exam?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "session_id" in data

    def test_post_chat_empty_message_fails(self):
        resp = client.post("/api/v1/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_post_chat_too_long_fails(self):
        resp = client.post("/api/v1/chat", json={"message": "x" * 501})
        assert resp.status_code == 422

    def test_get_history(self):
        resp = client.get("/api/v1/chat/history/nonexistent-session")
        assert resp.status_code == 200
        data = resp.json()
        assert "messages" in data

    def test_delete_session(self):
        resp = client.delete("/api/v1/chat/session/test-session-id")
        assert resp.status_code == 200


# ── Circulars ─────────────────────────────────────────────────────────────────

class TestCircularsEndpoint:
    @patch("backend.api.routes.circulars._service")
    def test_list_circulars(self, mock_service):
        mock_service.get_all_circulars.return_value = ([], 0)
        resp = client.get("/api/v1/circulars")
        assert resp.status_code == 200
        data = resp.json()
        assert "circulars" in data
        assert "total" in data

    @patch("backend.api.routes.circulars._service")
    def test_get_circular_not_found(self, mock_service):
        mock_service.get_circular_by_id.return_value = None
        resp = client.get("/api/v1/circulars/9999")
        assert resp.status_code == 404


# ── Exam Schedule ─────────────────────────────────────────────────────────────

class TestScheduleEndpoint:
    @patch("backend.api.routes.schedule._service")
    def test_get_schedule(self, mock_service):
        mock_service.get_schedule.return_value = []
        resp = client.get("/api/v1/exam-schedule?semester=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "schedules" in data

    @patch("backend.api.routes.schedule._service")
    def test_invalid_semester_fails(self, mock_service):
        resp = client.get("/api/v1/exam-schedule?semester=9")
        assert resp.status_code == 422

    @patch("backend.api.routes.schedule._service")
    def test_upcoming_exams(self, mock_service):
        mock_service.get_upcoming_exams.return_value = []
        resp = client.get("/api/v1/exam-schedule/upcoming")
        assert resp.status_code == 200


# ── Subscribe ─────────────────────────────────────────────────────────────────

class TestSubscribeEndpoint:
    @patch("backend.api.routes.notifications._user_service")
    def test_subscribe_valid(self, mock_service):
        mock_user = MagicMock()
        mock_user.id = 1
        mock_service.create_user.return_value = mock_user
        mock_service.create_subscription.return_value = []

        resp = client.post("/api/v1/subscribe", json={
            "email": "test@example.com",
            "name": "Test User",
            "semester": 5,
            "branch": "CSE",
            "channels": ["email"],
        })
        assert resp.status_code == 200
        assert resp.json()["user_id"] == 1

    def test_subscribe_invalid_email_fails(self):
        resp = client.post("/api/v1/subscribe", json={
            "email": "not-an-email",
            "name": "Test",
            "channels": ["email"],
        })
        assert resp.status_code == 422

    def test_subscribe_invalid_channel_fails(self):
        resp = client.post("/api/v1/subscribe", json={
            "email": "test@example.com",
            "name": "Test",
            "channels": ["whatsapp"],
        })
        assert resp.status_code == 422
