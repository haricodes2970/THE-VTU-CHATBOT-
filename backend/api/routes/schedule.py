"""
backend/api/routes/schedule.py
Exam schedule endpoints — filter by semester/branch/subject, upcoming exams.
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.services.schedule_service import ScheduleService

router = APIRouter()
_service = ScheduleService()


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


@router.get(
    "/exam-schedule",
    response_model=ExamScheduleListResponse,
    summary="Get exam schedule",
    description="Filter exam schedule by semester, branch, or subject name.",
)
def get_schedule(
    semester: Optional[int] = Query(None, ge=1, le=8),
    branch: Optional[str] = None,
    subject: Optional[str] = None,
    db: Session = Depends(get_db),
):
    rows = _service.get_schedule(db, semester=semester, branch=branch, subject=subject)
    return ExamScheduleListResponse(
        schedules=[
            ExamScheduleResponse(
                id=r.id,
                subject=r.subject,
                subject_code=r.subject_code,
                semester=r.semester,
                exam_date=str(r.exam_date) if r.exam_date else None,
                exam_time=r.exam_time,
                branch=r.branch,
                academic_year=r.academic_year,
            )
            for r in rows
        ],
        total=len(rows),
    )


@router.get(
    "/exam-schedule/upcoming",
    response_model=ExamScheduleListResponse,
    summary="Get upcoming exams in the next 7 days",
)
def get_upcoming_exams(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db),
):
    rows = _service.get_upcoming_exams(db, days=days)
    return ExamScheduleListResponse(
        schedules=[
            ExamScheduleResponse(
                id=r.id,
                subject=r.subject,
                subject_code=r.subject_code,
                semester=r.semester,
                exam_date=str(r.exam_date) if r.exam_date else None,
                exam_time=r.exam_time,
                branch=r.branch,
                academic_year=r.academic_year,
            )
            for r in rows
        ],
        total=len(rows),
    )
