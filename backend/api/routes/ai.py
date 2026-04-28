from __future__ import annotations
import asyncio
from datetime import date
from fastapi import APIRouter, HTTPException, Depends

from backend.core.ai_engine import (
    generate_briefing,
    get_anomalies,
    get_anomaly_detail,
    get_anomalies_for_month,
    invalidate_anomaly_cache,
)
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

_DETECTION_TYPES = ("amount_spike", "new_merchant", "frequency_spike", "duplicate_suspect", "unusual_time")


@router.get("/briefing")
async def briefing():
    """Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h."""
    # generate_briefing chiama Groq (I/O) — eseguito in thread pool per non bloccare l'event loop
    return await asyncio.to_thread(generate_briefing)


@router.get("/anomalies")
async def list_anomalies(
    current_user_id: str = Depends(get_current_user),
):
    """
    Ritorna anomalie del mese corrente.
    Usa cache in memoria se disponibile.
    """
    today = date.today()
    result = await asyncio.to_thread(
        get_anomalies_for_month,
        current_user_id,
        today.year,
        today.month,
        False,  # force_refresh
    )
    return result


@router.post("/anomalies/refresh")
async def refresh_anomalies(
    current_user_id: str = Depends(get_current_user),
):
    """
    Utente clicca 'Refresh anomalies'.
    Ricalcola con force_refresh=True per il mese corrente.
    """
    today = date.today()

    # Invalida cache per il mese corrente
    await asyncio.to_thread(
        invalidate_anomaly_cache,
        current_user_id,
        today.year,
        today.month,
    )

    # Ricalcola
    result = await asyncio.to_thread(
        get_anomalies_for_month,
        current_user_id,
        today.year,
        today.month,
        True,  # force_refresh
    )

    return result


@router.get("/anomalies/{tx_id}")
async def anomaly_detail(tx_id: int, detection_type: str = "amount_spike"):
    """Dettaglio statistico completo per una singola anomalia (calcolato on-demand)."""
    detail = await asyncio.to_thread(get_anomaly_detail, tx_id, detection_type)
    if detail is None:
        raise HTTPException(status_code=404, detail="Transazione non trovata")
    return detail
