"""backend/api/routes/chat.py — stub (implemented in Phase 4)"""
from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
async def chat():
    return {"message": "Chat endpoint — coming in Phase 4"}
