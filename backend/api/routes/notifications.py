"""backend/api/routes/notifications.py — stub"""
from fastapi import APIRouter
router = APIRouter()

@router.get("/notifications")
async def get_notifications():
    return {"notifications": [], "message": "Notifications endpoint — coming in Phase 7"}

@router.post("/subscribe")
async def subscribe():
    return {"message": "Subscribe endpoint — coming in Phase 7"}
