from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import json

from backend.core.database import get_db, ChatHistory
from backend.core.ai_engine import chat_with_ai
from backend.api.models.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Endpoint chat: domanda in linguaggio naturale → analisi AI."""
    try:
        result = chat_with_ai(request.message, request.history)
    except Exception as e:
        raise HTTPException(500, f"Errore AI: {str(e)}")

    # Salva in chat_history
    db.add(ChatHistory(role="user", content=request.message))
    db.add(ChatHistory(
        role="assistant",
        content=result["answer"],
        metadata_json=json.dumps({
            "chart": result["chart"] is not None,
            "followups": result["followup_questions"],
        }),
    ))
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        chart=result["chart"],
        data_table=result["data_table"],
        followup_questions=result["followup_questions"],
    )


@router.get("/history")
async def get_chat_history(limit: int = 20, db: Session = Depends(get_db)):
    """Recupera la cronologia chat."""
    rows = (
        db.query(ChatHistory)
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
