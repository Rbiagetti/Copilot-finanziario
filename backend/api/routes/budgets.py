from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.core.database import get_db, Budget, Transaction
from backend.api.models.schemas import BudgetCreate, BudgetResponse
from datetime import date

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


@router.post("/", response_model=BudgetResponse)
async def create_budget(data: BudgetCreate, db: Session = Depends(get_db)):
    budget = Budget(category=data.category, amount=data.amount, period=data.period)
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(db: Session = Depends(get_db)):
    return db.query(Budget).filter(Budget.active == True).all()


@router.delete("/{budget_id}")
async def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.id == budget_id).first()
    if not b:
        raise HTTPException(404, "Budget non trovato")
    b.active = False
    db.commit()
    return {"detail": "Budget disattivato"}


@router.get("/status")
async def budget_status(db: Session = Depends(get_db)):
    """Stato budget: quanto speso vs budget per ogni categoria."""
    budgets = db.query(Budget).filter(Budget.active == True).all()
    today = date.today()
    first_of_month = today.replace(day=1)

    result = []
    for b in budgets:
        spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.category == b.category,
                Transaction.date >= first_of_month.isoformat(),
            )
            .scalar()
        )
        pct = round((spent / b.amount) * 100, 1) if b.amount > 0 else 0
        result.append({
            "category": b.category,
            "budget": b.amount,
            "spent": round(spent, 2),
            "remaining": round(b.amount - spent, 2),
            "percentage": pct,
            "status": "over" if pct >= 100 else "warning" if pct >= 80 else "ok",
        })

    return result
