from __future__ import annotations
from fastapi import APIRouter, HTTPException

from backend.core.ai_engine import generate_briefing, get_anomalies, get_anomaly_detail

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_DETECTION_TYPES = ("amount_spike", "new_merchant", "frequency_spike", "duplicate_suspect", "unusual_time")


@router.get("/briefing")
async def briefing():
    """Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h."""
    return generate_briefing()


@router.get("/anomalies")
async def anomalies():
    """Anomalie multi-tipo (5 detector) sugli ultimi 60-90gg."""
    items = get_anomalies()
    by_type = {t: 0 for t in _DETECTION_TYPES}
    for item in items:
        dt = item.get("detection_type", "amount_spike")
        if dt in by_type:
            by_type[dt] += 1
    return {"anomalies": items, "count": len(items), "by_type": by_type}


@router.get("/anomalies/{tx_id}")
async def anomaly_detail(tx_id: int, detection_type: str = "amount_spike"):
    """Dettaglio statistico completo per una singola anomalia (calcolato on-demand)."""
    detail = get_anomaly_detail(tx_id, detection_type)
    if detail is None:
        raise HTTPException(status_code=404, detail="Transazione non trovata")
    return detail
