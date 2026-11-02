from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import date, datetime

from backend.core.categories import STANDARD_CATEGORIES as CATEGORIES


class TransactionCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Importo in euro")
    category: str = Field(..., description="Categoria spesa")
    description: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    account: str = "principale"
    tags: Optional[str] = None
    source: str = "manual"


class TransactionResponse(BaseModel):
    id: int
    amount: float
    category: str
    description: Optional[str]
    date: str
    time: Optional[str]
    account: str
    source: str
    tags: Optional[str]
    is_recurring: Optional[bool]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None
    tags: Optional[str] = None
    is_recurring: Optional[bool] = None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Domanda in linguaggio naturale")
    history: List[Dict] = Field(default_factory=list)


class ReasoningStep(BaseModel):
    phase:       str
    label:       str
    detail:      str
    duration_ms: int
    status:      str


class ChatResponse(BaseModel):
    answer: str
    chart_data: Optional[Dict] = None
    data_table: Optional[Dict] = None
    followup_questions: List[str] = Field(default_factory=list)
    reasoning_steps: List[ReasoningStep] = Field(default_factory=list)


class BudgetCreate(BaseModel):
    category: str
    amount: float = Field(..., gt=0)
    period: str = "monthly"


class BudgetResponse(BaseModel):
    id: int
    category: str
    amount: float
    period: str
    active: bool
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    total_month: float
    total_prev_month: float
    variation_pct: float
    top_category: str
    by_category: List[Dict]
    daily_trend: List[Dict]


class FullHistoryResponse(BaseModel):
    id: int
    amount: float
    category: str
    date: str
    time: Optional[str] = None
    account: str = "principale"
    tags: Optional[str] = None
    is_recurring: Optional[bool] = False

    class Config:
        from_attributes = True


# ─── Wealth Monitor ───────────────────────────────────────────────────────────

# Tipi di conto ammessi. Slug senza accenti, usati come valore persistito e come
# chiave di composizione; le etichette italiane vivono solo nel frontend.
WEALTH_KINDS = ["liquidita", "investimenti", "previdenza", "immobili", "altro"]


class WealthAccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    kind: str = "liquidita"


class WealthAccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=40)
    kind: Optional[str] = None


class WealthAccountResponse(BaseModel):
    id: int
    name: str
    kind: str

    class Config:
        from_attributes = True


class WealthSnapshotEntry(BaseModel):
    account_id: int
    balance: float = Field(..., ge=0, le=100_000_000)


class WealthSnapshotSave(BaseModel):
    date: str
    entries: List[WealthSnapshotEntry] = Field(..., min_length=1, max_length=100)
