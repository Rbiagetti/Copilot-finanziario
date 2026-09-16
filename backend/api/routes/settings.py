from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.core.database import get_db
from backend.core.ai_engine import (
    get_model_for_user,
    set_model_for_user,
    list_available_models,
    DEFAULT_MODEL,
)
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


class AiModelUpdate(BaseModel):
    model: str


@router.get("/ai-model")
async def get_ai_model_settings(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Modello AI attivo per l'utente, il default globale e la lista dei modelli
    testuali disponibili su Groq — usati dal selettore in Impostazioni."""
    current = get_model_for_user(db, current_user_id)
    try:
        available = list_available_models()
    except Exception:
        available = []
    valid_ids = {m["id"] for m in available}
    return {
        "current": current,
        "default": DEFAULT_MODEL,
        "available": available,
        "current_is_valid": (current in valid_ids) if available else None,
    }


@router.put("/ai-model")
async def update_ai_model_settings(
    data: AiModelUpdate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Imposta la preferenza di modello AI per l'utente corrente (non tocca gli altri)."""
    try:
        available = list_available_models()
    except Exception:
        raise HTTPException(502, "Impossibile verificare i modelli disponibili su Groq al momento.")
    if data.model not in {m["id"] for m in available}:
        raise HTTPException(400, "Modello non valido o non disponibile su Groq.")
    set_model_for_user(db, current_user_id, data.model)
    return {"current": data.model}
