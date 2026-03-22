from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import date, timedelta
from collections import defaultdict

from backend.core.database import get_db, Transaction
from backend.api.models.schemas import DashboardResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(db: Session = Depends(get_db)):
    """Dashboard overview: totali, variazione, categorie, trend giornaliero."""
    today = date.today()
    first_of_month = today.replace(day=1)
    if today.month == 1:
        first_prev = today.replace(year=today.year - 1, month=12, day=1)
    else:
        first_prev = today.replace(month=today.month - 1, day=1)

    # Totale mese corrente
    total_month = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.date >= first_of_month.isoformat())
        .scalar()
    )

    # Totale mese precedente
    total_prev = (
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(
            Transaction.date >= first_prev.isoformat(),
            Transaction.date < first_of_month.isoformat(),
        )
        .scalar()
    )

    variation = ((total_month - total_prev) / total_prev * 100) if total_prev > 0 else 0

    # Spese per categoria (mese corrente)
    cat_rows = (
        db.query(Transaction.category, func.sum(Transaction.amount))
        .filter(Transaction.date >= first_of_month.isoformat())
        .group_by(Transaction.category)
        .all()
    )
    by_category = [{"category": c, "total": round(t, 2)} for c, t in cat_rows]
    top_category = max(by_category, key=lambda x: x["total"])["category"] if by_category else "nessuna"

    # Trend giornaliero (ultimi 30 giorni)
    thirty_ago = (today - timedelta(days=30)).isoformat()
    daily_rows = (
        db.query(Transaction.date, func.sum(Transaction.amount))
        .filter(Transaction.date >= thirty_ago)
        .group_by(Transaction.date)
        .order_by(Transaction.date)
        .all()
    )
    daily_trend = [{"date": d, "total": round(t, 2)} for d, t in daily_rows]

    return DashboardResponse(
        total_month=round(total_month, 2),
        total_prev_month=round(total_prev, 2),
        variation_pct=round(variation, 1),
        top_category=top_category,
        by_category=by_category,
        daily_trend=daily_trend,
    )
