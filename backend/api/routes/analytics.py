from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from typing import List, Optional, Dict
import calendar

from backend.core.database import get_db, Transaction
from backend.api.models.schemas import DashboardResponse, FullHistoryResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/full-history", response_model=List[FullHistoryResponse])
async def get_full_history(db: Session = Depends(get_db)):
    """Restituisce tutte le transazioni con campi minimi per aggregazione frontend."""
    return db.query(Transaction).order_by(Transaction.date.desc()).all()


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
    daily_map = {d: round(t, 2) for d, t in daily_rows}
    daily_trend = [
        {"date": (today - timedelta(days=29-i)).isoformat(), "total": daily_map.get((today - timedelta(days=29-i)).isoformat(), 0.0)}
        for i in range(30)
    ]

    return DashboardResponse(
        total_month=round(total_month, 2),
        total_prev_month=round(total_prev, 2),
        variation_pct=round(variation, 1),
        top_category=top_category,
        by_category=by_category,
        daily_trend=daily_trend,
    )


@router.get("/forecast")
async def get_forecast(db: Session = Depends(get_db)):
    """Proiezione spese a fine mese basata su media mobile ponderata (ultimi 14gg)."""
    today = date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    days_remaining = days_in_month - days_elapsed

    # Daily totals ultimi 14gg
    fourteen_ago = (today - timedelta(days=14)).isoformat()
    daily_rows = (
        db.query(Transaction.date, func.sum(Transaction.amount))
        .filter(Transaction.date >= fourteen_ago)
        .group_by(Transaction.date)
        .order_by(Transaction.date)
        .all()
    )

    if not daily_rows:
        return {
            "projected_total": 0.0,
            "month_so_far": 0.0,
            "daily_burn_rate": 0.0,
            "days_remaining": days_remaining,
            "confidence": "low",
        }

    # Media mobile ponderata (i giorni più recenti pesano di più)
    n = len(daily_rows)
    weights = list(range(1, n + 1))
    total_weight = sum(weights)
    daily_burn = sum(w * float(r[1]) for w, r in zip(weights, daily_rows)) / total_weight

    # Spese mese corrente fino ad oggi
    first_of_month = today.replace(day=1)
    month_so_far = float(
        db.query(func.coalesce(func.sum(Transaction.amount), 0))
        .filter(Transaction.date >= first_of_month.isoformat())
        .scalar()
    )

    projected_total = month_so_far + (daily_burn * days_remaining)
    confidence = "high" if n >= 10 else "medium" if n >= 5 else "low"

    return {
        "projected_total": round(projected_total, 2),
        "month_so_far": round(month_so_far, 2),
        "daily_burn_rate": round(daily_burn, 2),
        "days_remaining": days_remaining,
        "confidence": confidence,
    }


@router.get("/monthly-history")
async def get_monthly_history(months: int = 6, db: Session = Depends(get_db)):
    """Totale spese per mese negli ultimi N mesi."""
    today = date.today()
    result = []
    for i in range(months - 1, -1, -1):
        # calcola primo e ultimo giorno del mese target
        month_date = date(today.year, today.month, 1)
        # sottrai i mesi
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        first = date(y, m, 1)
        last_day = calendar.monthrange(y, m)[1]
        last = date(y, m, last_day)

        total = float(
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.date >= first.isoformat(),
                Transaction.date <= last.isoformat(),
            )
            .scalar()
        )
        result.append({
            "month": first.strftime("%Y-%m"),
            "label": first.strftime("%b %Y"),
            "total": round(total, 2),
        })
    return result
