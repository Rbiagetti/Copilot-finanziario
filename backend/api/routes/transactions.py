from __future__ import annotations
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime
import csv, io

from pydantic import BaseModel

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
    search: Optional[str] = None,
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
    if search:
        term = f"%{search.lower()}%"
        from sqlalchemy import or_, func as sqlfunc
        q = q.filter(or_(
            sqlfunc.lower(Transaction.description).like(term),
            sqlfunc.lower(Transaction.category).like(term),
        ))
    q = q.order_by(desc(Transaction.date), desc(Transaction.id))
    return q.offset(offset).limit(limit).all()


@router.get("/count")
async def count_transactions(
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Conta transazioni con gli stessi filtri e restituisce anche il totale €."""
    from sqlalchemy import func as sqlfunc, or_
    q = db.query(
        sqlfunc.count(Transaction.id),
        sqlfunc.coalesce(sqlfunc.sum(Transaction.amount), 0),
    )
    if category:
        q = q.filter(Transaction.category == category)
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(or_(
            sqlfunc.lower(Transaction.description).like(term),
            sqlfunc.lower(Transaction.category).like(term),
        ))
    count, total = q.one()
    return {"count": count, "total": round(float(total), 2)}


@router.get("/export")
async def export_transactions_csv(
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Esporta transazioni in formato CSV con gli stessi filtri della lista."""
    from sqlalchemy import or_, func as sqlfunc
    q = db.query(Transaction)
    if category:
        q = q.filter(Transaction.category == category)
    if date_from:
        q = q.filter(Transaction.date >= date_from)
    if date_to:
        q = q.filter(Transaction.date <= date_to)
    if search:
        term = f"%{search.lower()}%"
        q = q.filter(or_(
            sqlfunc.lower(Transaction.description).like(term),
            sqlfunc.lower(Transaction.category).like(term),
        ))
    q = q.order_by(desc(Transaction.date), desc(Transaction.id))
    txs = q.all()

    parts = ["fincopilot"]
    if category:
        parts.append(category)
    if date_from:
        parts.append(f"dal_{date_from}")
    if date_to:
        parts.append(f"al_{date_to}")
    parts.append(date.today().isoformat())
    filename = "_".join(parts) + ".csv"

    buf = io.BytesIO()
    buf.write(b"\xef\xbb\xbf")  # BOM UTF-8 per Excel Windows
    wrapper = io.TextIOWrapper(buf, encoding="utf-8", newline="")
    writer = csv.writer(wrapper)
    writer.writerow(["data", "ora", "categoria", "descrizione", "importo_eur", "account", "tags", "ricorrente", "id"])
    for t in txs:
        writer.writerow([
            t.date,
            t.time or "",
            t.category,
            t.description or "",
            str(round(t.amount, 2)),
            t.account,
            t.tags or "",
            "sì" if t.is_recurring else "no",
            t.id,
        ])
    wrapper.flush()
    buf.seek(0)

    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


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


class NLParseRequest(BaseModel):
    text: str


@router.post("/parse-natural")
async def parse_natural_language(data: NLParseRequest, db: Session = Depends(get_db)):
    """Parsa testo in linguaggio naturale e crea una transazione."""
    import os, json
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("GROQ_API_KEY", ""),
        base_url="https://api.groq.com/openai/v1",
    )

    system_prompt = (
        "Sei un parser di spese personali. "
        "Estrai da testo libero in italiano: importo, categoria e nota. "
        "Rispondi SOLO con JSON valido, nessun testo extra. "
        f'Formato: {{"amount": float, "category": str, "note": str}} '
        f"Categorie disponibili: {', '.join(CATEGORIES)} "
        "Se la categoria non è chiara, usa 'altro'. "
        "Se manca l'importo, usa 0.0."
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": data.text},
        ],
        temperature=0,
        max_tokens=100,
    )

    raw = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(400, "Impossibile interpretare il testo")

    if parsed.get("amount", 0) <= 0:
        raise HTTPException(400, "Importo non trovato nel testo")

    tx = Transaction(
        amount=parsed["amount"],
        category=parsed.get("category", "altro"),
        description=parsed.get("note", ""),
        date=date.today().isoformat(),
        time=datetime.now().strftime("%H:%M"),
        source="natural",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
