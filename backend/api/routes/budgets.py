from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.core.database import get_db, Budget, Transaction
from backend.api.models.schemas import BudgetCreate, BudgetResponse
from backend.api.auth import get_current_user
from datetime import date

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])


@router.post("/", response_model=BudgetResponse)
async def create_budget(
    data: BudgetCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    budget = Budget(
        user_id=current_user_id,
        category=data.category,
        amount=data.amount,
        period=data.period
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(Budget).filter(
        (Budget.active == True) & (Budget.user_id == current_user_id)
    ).all()


@router.put("/{budget_id}")
async def update_budget(
    budget_id: int,
    data: BudgetCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    b = db.query(Budget).filter(
        (Budget.id == budget_id) & (Budget.active == True) & (Budget.user_id == current_user_id)
    ).first()
    if not b:
        raise HTTPException(404, "Budget non trovato")
    b.amount = data.amount
    b.category = data.category
    db.commit()
    db.refresh(b)
    return b


@router.delete("/{budget_id}")
async def delete_budget(
    budget_id: int,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    b = db.query(Budget).filter(
        (Budget.id == budget_id) & (Budget.user_id == current_user_id)
    ).first()
    if not b:
        raise HTTPException(404, "Budget non trovato")
    b.active = False
    db.commit()
    return {"detail": "Budget disattivato"}


@router.get("/status")
async def budget_status(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stato budget: quanto speso vs budget per ogni categoria — filtrato per user_id."""
    budgets = db.query(Budget).filter(
        (Budget.active == True) & (Budget.user_id == current_user_id)
    ).all()
    today = date.today()
    first_of_month = today.replace(day=1)

    result = []
    for b in budgets:
        spent = (
            db.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                (Transaction.category == b.category) & (Transaction.user_id == current_user_id),
                Transaction.date >= first_of_month.isoformat(),
            )
            .scalar()
        )
        pct = round((spent / b.amount) * 100, 1) if b.amount > 0 else 0
        result.append({
            "id": b.id,
            "category": b.category,
            "budget": b.amount,
            "spent": round(spent, 2),
            "remaining": round(b.amount - spent, 2),
            "percentage": pct,
            "status": "over" if pct >= 100 else "warning" if pct >= 80 else "ok",
        })

    return result
