"""
backend/api/schemas.py
Centralised Pydantic request/response schemas for all API endpoints.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None

    @field_validator("message")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class SourceItem(BaseModel):
    title: str = ""
    url: str = ""
    score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    intent: str
    entities: dict
    sources: list[SourceItem]
    session_id: str
    response_time_ms: int
    confidence: str  # HIGH | MEDIUM | LOW


# ── Circulars ─────────────────────────────────────────────────────────────────

class CircularResponse(BaseModel):
    id: int
    title: str
    url: str
    pdf_path: Optional[str] = None
    content: Optional[str] = None
    circular_date: Optional[str] = None
    is_processed: bool
    is_indexed: bool
    scraped_at: str

    model_config = {"from_attributes": True}


class CircularListResponse(BaseModel):
    circulars: list[CircularResponse]
    total: int
    page: int
    limit: int


# ── Exam Schedule ─────────────────────────────────────────────────────────────

class ExamScheduleResponse(BaseModel):
    id: int
    subject: str
    subject_code: Optional[str] = None
    semester: Optional[int] = None
    exam_date: Optional[str] = None
    exam_time: Optional[str] = None
    branch: Optional[str] = None
    academic_year: Optional[str] = None

    model_config = {"from_attributes": True}


class ExamScheduleListResponse(BaseModel):
    schedules: list[ExamScheduleResponse]
    total: int


# ── Subscribe / Notifications ─────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)
    semester: Optional[int] = Field(None, ge=1, le=8)
    branch: Optional[str] = Field(None, max_length=50)
    channels: list[str] = Field(default=["email"])

    @field_validator("channels")
    @classmethod
    def validate_channels(cls, v: list[str]) -> list[str]:
        valid = {"email", "telegram"}
        for ch in v:
            if ch not in valid:
                raise ValueError(f"Invalid channel: {ch}. Must be one of {valid}")
        return v


class SubscribeResponse(BaseModel):
    user_id: int
    message: str


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    channel: str
    status: str
    sent_at: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    app: str
    env: str
    database: str


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str = ""
    status_code: int
    timestamp: str
