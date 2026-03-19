"""backend/api/routes/schedule.py — stub"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/exam-schedule")
async def get_schedule():
    return {"schedules": [], "message": "Schedule endpoint — coming in Phase 3"}
