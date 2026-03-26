from __future__ import annotations
from fastapi import APIRouter

from backend.core.ai_engine import generate_briefing, get_anomalies

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/briefing")
async def briefing():
    """Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h."""
    return generate_briefing()


@router.get("/anomalies")
async def anomalies():
    """Transazioni anomale (z-score > 1.5 per categoria, ultimi 60gg)."""
    items = get_anomalies()
    return {"anomalies": items, "count": len(items)}
