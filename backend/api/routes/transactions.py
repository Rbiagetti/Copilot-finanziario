from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime

from backend.core.database import get_db, Transaction
from backend.api.models.schemas import (
    TransactionCreate, TransactionResponse, TransactionUpdate, CATEGORIES
)

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.post("/", response_model=TransactionResponse)
async def create_transaction(data: TransactionCreate, db: Session = Depends(get_db)):
    """Crea una nuova transazione."""
    if data.category not in CATEGORIES:
        data.category = "altro"

    tx = Transaction(
        amount=data.amount,
        category=data.category,
        description=data.description,
        date=data.date or date.today().isoformat(),
        time=data.time or datetime.now().strftime("%H:%M"),
        account=data.account,
        tags=data.tags,
        source=data.source,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


@router.get("/", response_model=list[TransactionResponse])
async def list_transactions(
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Lista transazioni con filtri opzionali."""
    q = db.query(Transaction)
    if category:
        q = q.filter(Transaction.category == category)
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)
    q = q.order_by(desc(Transaction.date), desc(Transaction.id))
    return q.offset(offset).limit(limit).all()


@router.get("/{tx_id}", response_model=TransactionResponse)
async def get_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(404, "Transazione non trovata")
    return tx


@router.put("/{tx_id}", response_model=TransactionResponse)
async def update_transaction(tx_id: int, data: TransactionUpdate, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(404, "Transazione non trovata")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    db.commit()
    db.refresh(tx)
    return tx


@router.delete("/{tx_id}")
async def delete_transaction(tx_id: int, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == tx_id).first()
    if not tx:
        raise HTTPException(404, "Transazione non trovata")
    db.delete(tx)
    db.commit()
    return {"detail": "Transazione eliminata"}


@router.get("/stats/categories")
async def categories_list():
    """Ritorna le categorie disponibili."""
    return {"categories": CATEGORIES}
