"""backend/api/routes/circulars.py — stub (implemented in Phase 2)"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/circulars")
async def get_circulars():
    return {"circulars": [], "message": "Circulars endpoint — coming in Phase 2"}
