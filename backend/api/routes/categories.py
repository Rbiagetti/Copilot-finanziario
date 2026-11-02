from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.database import get_db, Category
from backend.core.categories import CATEGORIES, STANDARD_CATEGORIES, get_active_category_names
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])

MAX_CUSTOM_CATEGORY_LEN = 30


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=MAX_CUSTOM_CATEGORY_LEN)


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


@router.get("/")
async def list_categories(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ritorna le standard (fisse) e le personalizzate attive dell'utente, separate —
    il frontend le unisce per i menu ma le mostra distinte in Impostazioni (solo le
    personalizzate sono eliminabili)."""
    custom = db.query(Category).filter(
        Category.user_id == current_user_id, Category.active == True
    ).order_by(Category.created_at).all()
    return {
        "standard": STANDARD_CATEGORIES,
        "custom": [{"id": c.id, "name": c.name} for c in custom],
    }


@router.post("/", response_model=CategoryResponse)
async def create_category(
    data: CategoryCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = data.name.strip().lower()
    if not name:
        raise HTTPException(400, "Il nome della categoria non può essere vuoto")

    if name in CATEGORIES:
        raise HTTPException(409, f"'{name}' è già una categoria standard dell'app")

    existing = db.query(Category).filter(
        Category.user_id == current_user_id,
        Category.name == name,
        Category.active == True,
    ).first()
    if existing:
        raise HTTPException(409, f"Hai già una categoria personalizzata '{name}'")

    cat = Category(user_id=current_user_id, name=name, active=True)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/{category_id}")
async def delete_category(
    category_id: int,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete: disattiva, non cancella. Le transazioni storiche con questa categoria
    restano intatte — la categoria sparisce solo dai menu per le nuove transazioni."""
    cat = db.query(Category).filter(
        Category.id == category_id,
        Category.user_id == current_user_id,
        Category.active == True,
    ).first()
    if not cat:
        raise HTTPException(404, "Categoria non trovata")
    cat.active = False
    db.commit()
    return {"detail": "Categoria disattivata"}
