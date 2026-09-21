from __future__ import annotations
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.core.ai_engine import (
    generate_briefing,
    activate_model_for_request,
)
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/briefing")
async def briefing(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h — filtrato per user_id."""
    activate_model_for_request(db, current_user_id)
    # generate_briefing chiama Groq (I/O) — eseguito in thread pool per non bloccare l'event loop
    return await asyncio.to_thread(generate_briefing, current_user_id)
