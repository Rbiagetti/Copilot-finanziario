from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from backend.core.database import get_db, ChatHistory
from backend.core.ai_engine import chat_with_ai, get_llm_stats, MAX_QUESTION_CHARS
from backend.api.models.schemas import ChatRequest, ChatResponse
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Endpoint chat: domanda in linguaggio naturale → analisi AI."""
    # Block C: guardrail input — truncate + reject empty
    message = (request.message or "").strip()[:MAX_QUESTION_CHARS]
    if not message:
        raise HTTPException(status_code=400, detail="Messaggio vuoto")

    try:
        result = chat_with_ai(message, request.history)
    except Exception as e:
        raise HTTPException(500, f"Errore AI: {str(e)}")

    # Salva in chat_history con user_id
    db.add(ChatHistory(role="user", content=message, user_id=current_user_id))
    db.add(ChatHistory(
        role="assistant",
        content=result["answer"],
        user_id=current_user_id,
        metadata_json=json.dumps({
            "chart_data": result["chart_data"] is not None,
            "followups": result["followup_questions"],
        }),
    ))
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        chart_data=result["chart_data"],
        data_table=result["data_table"],
        followup_questions=result["followup_questions"],
        reasoning_steps=result.get("reasoning_steps", []),
    )


@router.get("/history")
async def get_chat_history(
    limit: int = 20,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Recupera la cronologia chat filtrata per user_id."""
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == current_user_id)
        .order_by(ChatHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reversed(rows)
    ]


@router.get("/stats")
async def get_chat_stats():
    """Statistiche chiamate LLM dall'avvio del processo (debug/monitoring)."""
    return get_llm_stats()
