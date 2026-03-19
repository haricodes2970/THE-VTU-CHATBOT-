"""
tests/conftest.py
Shared pytest fixtures: in-memory SQLite DB, sample objects, mock settings, test client.
"""
import pytest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.models.models import (
    User, Circular, ExamSchedule, Subscription,
    Notification, NotificationChannel, NotificationStatus,
)


# ── Test database (SQLite in-memory) ─────────────────────────────────────────

TEST_DB_URL = "sqlite:///./test.db"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    """Provide a clean test DB session that rolls back after each test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """FastAPI TestClient with DB dependency overridden to use SQLite."""
    from backend.main import app

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


# ── Sample model fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def sample_user(db):
    user = User(
        email="test@vtu.ac.in",
        name="Test Student",
        semester=5,
        branch="CSE",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def sample_circular(db):
    circ = Circular(
        title="5th Semester Exam Schedule November 2025",
        url="https://vtu.ac.in/circulars/5th-sem-2025.pdf",
        content=(
            "5th semester CSE examination schedule. "
            "DBMS exam on 10/12/2025 at 10:30 AM. "
            "OS exam on 12/12/2025 at 10:30 AM."
        ),
        circular_date=datetime(2025, 11, 1),
        is_processed=True,
        scraped_at=datetime.utcnow(),
    )
    db.add(circ)
    db.commit()
    db.refresh(circ)
    return circ


@pytest.fixture
def sample_exam(db, sample_circular):
    exam = ExamSchedule(
        subject="Database Management Systems",
        subject_code="CS501",
        semester=5,
        branch="CSE",
        exam_date=datetime(2025, 12, 10, 10, 30),
        exam_time="10:30 AM",
        academic_year="2025-26",
        circular_id=sample_circular.id,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@pytest.fixture
def sample_subscription(db, sample_user):
    sub = Subscription(
        user_id=sample_user.id,
        channel=NotificationChannel.EMAIL,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


# ── Mock settings ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings():
    """Override settings with test values (no real API keys needed)."""
    with patch("backend.core.config.settings") as mock:
        mock.app_env = "development"
        mock.is_development = True
        mock.is_production = False
        mock.groq_api_key = "test_groq_key"
        mock.pinecone_api_key = "test_pinecone_key"
        mock.pinecone_index_name = "test-index"
        mock.pinecone_dimension = 384
        mock.groq_model = "llama3-8b-8192"
        mock.secret_key = "test-secret-key"
        yield mock
