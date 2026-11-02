"""Wealth Monitor — patrimonio personale a snapshot.

Modello: l'utente definisce i propri conti (nome libero + tipo) e periodicamente
salva una "foto" dei saldi a una certa data. Il patrimonio mostrato è la somma delle
attività (nessuna passività in questa versione). Ogni endpoint è filtrato per user_id.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.api.auth import get_current_user
from backend.api.models.schemas import (
    WEALTH_KINDS,
    WealthAccountCreate,
    WealthAccountResponse,
    WealthAccountUpdate,
    WealthSnapshotSave,
)
from backend.core.database import WealthAccount, WealthSnapshot, get_db

router = APIRouter(prefix="/api/v1/wealth", tags=["wealth"])

DEFAULT_MONTHS = 12
MAX_MONTHS = 60
MAX_ACCOUNTS = 50


# ─── Helper ───────────────────────────────────────────────────────────────────

def _today() -> date:
    return date.today()


def _validate_date(raw: str | None) -> str:
    """Accetta solo date ISO valide e non future. Una data futura non ha senso per una
    foto del patrimonio e riprodurrebbe il bug storico delle transazioni future."""
    if not raw:
        return _today().isoformat()
    try:
        parsed = datetime.strptime(raw.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise HTTPException(422, "Data non valida: usa il formato YYYY-MM-DD")
    if parsed > _today():
        raise HTTPException(422, "La data non può essere nel futuro")
    return parsed.isoformat()


def _validate_kind(kind: str) -> str:
    if kind not in WEALTH_KINDS:
        raise HTTPException(
            422, f"Tipo di conto non valido. Ammessi: {', '.join(WEALTH_KINDS)}"
        )
    return kind


def _clean_name(raw: str) -> str:
    name = (raw or "").strip()
    if not name:
        raise HTTPException(422, "Il nome del conto non può essere vuoto")
    if len(name) > 40:
        raise HTTPException(422, "Il nome del conto non può superare 40 caratteri")
    return name


def _account_or_404(
    db: Session, account_id: int, user_id: str, *, only_active: bool = False
) -> WealthAccount:
    query = db.query(WealthAccount).filter(
        WealthAccount.id == account_id,
        WealthAccount.user_id == user_id,
    )
    if only_active:
        query = query.filter(WealthAccount.active == True)
    account = query.first()
    if not account:
        raise HTTPException(404, "Conto non trovato")
    return account


def _active_accounts(db: Session, user_id: str) -> list[WealthAccount]:
    return (
        db.query(WealthAccount)
        .filter(WealthAccount.user_id == user_id, WealthAccount.active == True)
        .order_by(WealthAccount.created_at, WealthAccount.id)
        .all()
    )


def _month_start(months_back: int) -> str:
    """Primo giorno del mese a `months_back` mesi da oggi (0 = mese corrente)."""
    today = _today()
    year, month = today.year, today.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1).isoformat()


def _all_snapshots(
    db: Session, user_id: str, account_ids: list[int]
) -> list[WealthSnapshot]:
    if not account_ids:
        return []
    return (
        db.query(WealthSnapshot)
        .filter(
            WealthSnapshot.user_id == user_id,
            WealthSnapshot.account_id.in_(account_ids),
        )
        .order_by(WealthSnapshot.snapshot_date.asc(), WealthSnapshot.id.asc())
        .all()
    )


def _latest_by_account(
    db: Session, user_id: str, account_ids: list[int], upto: str | None = None
) -> dict[int, WealthSnapshot]:
    if not account_ids:
        return {}
    query = db.query(WealthSnapshot).filter(
        WealthSnapshot.user_id == user_id,
        WealthSnapshot.account_id.in_(account_ids),
    )
    if upto:
        query = query.filter(WealthSnapshot.snapshot_date <= upto)
    rows = query.order_by(
        WealthSnapshot.snapshot_date.asc(), WealthSnapshot.id.asc()
    ).all()
    latest: dict[int, WealthSnapshot] = {}
    for row in rows:
        latest[row.account_id] = row
    return latest


# ─── Conti ────────────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=list[WealthAccountResponse])
def list_accounts(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _active_accounts(db, current_user_id)


@router.post("/accounts", response_model=WealthAccountResponse, status_code=201)
def create_account(
    data: WealthAccountCreate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    name = _clean_name(data.name)
    kind = _validate_kind(data.kind)

    if len(_active_accounts(db, current_user_id)) >= MAX_ACCOUNTS:
        raise HTTPException(422, f"Massimo {MAX_ACCOUNTS} conti attivi")

    duplicate = (
        db.query(WealthAccount)
        .filter(
            WealthAccount.user_id == current_user_id,
            WealthAccount.active == True,
            func.lower(WealthAccount.name) == name.lower(),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(409, f"Esiste già un conto attivo chiamato '{name}'")

    account = WealthAccount(user_id=current_user_id, name=name, kind=kind)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.patch("/accounts/{account_id}", response_model=WealthAccountResponse)
def update_account(
    account_id: int,
    data: WealthAccountUpdate,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _account_or_404(db, account_id, current_user_id)

    if data.name is not None:
        name = _clean_name(data.name)
        duplicate = (
            db.query(WealthAccount)
            .filter(
                WealthAccount.user_id == current_user_id,
                WealthAccount.active == True,
                WealthAccount.id != account_id,
                func.lower(WealthAccount.name) == name.lower(),
            )
            .first()
        )
        if duplicate:
            raise HTTPException(409, f"Esiste già un conto attivo chiamato '{name}'")
        account.name = name

    if data.kind is not None:
        account.kind = _validate_kind(data.kind)

    db.commit()
    db.refresh(account)
    return account


@router.delete("/accounts/{account_id}")
def archive_account(
    account_id: int,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft delete: il conto sparisce da form, composizione e totali, ma gli snapshot
    restano in DB (recuperabili a mano o in una futura funzione di ripristino)."""
    account = _account_or_404(db, account_id, current_user_id, only_active=True)
    account.active = False
    db.commit()
    return {"ok": True, "id": account_id}


# ─── Snapshot ─────────────────────────────────────────────────────────────────

@router.get("/snapshot")
def get_snapshot(
    date_str: str | None = Query(None, alias="date"),
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Prefill del form: ultimo saldo noto (alla data o prima) per ogni conto attivo."""
    snapshot_date = _validate_date(date_str)
    accounts = _active_accounts(db, current_user_id)
    latest = _latest_by_account(
        db, current_user_id, [a.id for a in accounts], upto=snapshot_date
    )
    return {
        "date": snapshot_date,
        "accounts": [
            {
                "account_id": account.id,
                "name": account.name,
                "kind": account.kind,
                "balance": latest[account.id].balance if account.id in latest else None,
                "balance_date": (
                    latest[account.id].snapshot_date if account.id in latest else None
                ),
            }
            for account in accounts
        ],
    }


@router.put("/snapshot")
def save_snapshot(
    data: WealthSnapshotSave,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upsert bulk: per ogni conto aggiorna lo snapshot della data indicata, o lo crea.
    Salvare due volte la stessa data non produce duplicati."""
    snapshot_date = _validate_date(data.date)
    account_ids = [entry.account_id for entry in data.entries]

    if len(account_ids) != len(set(account_ids)):
        raise HTTPException(422, "Lo stesso conto compare più volte nella foto")

    owned = (
        db.query(WealthAccount)
        .filter(
            WealthAccount.user_id == current_user_id,
            WealthAccount.id.in_(account_ids),
            WealthAccount.active == True,
        )
        .all()
    )
    owned_ids = {account.id for account in owned}
    missing = [account_id for account_id in account_ids if account_id not in owned_ids]
    if missing:
        raise HTTPException(404, f"Conto non trovato: {missing[0]}")

    existing = (
        db.query(WealthSnapshot)
        .filter(
            WealthSnapshot.user_id == current_user_id,
            WealthSnapshot.account_id.in_(account_ids),
            WealthSnapshot.snapshot_date == snapshot_date,
        )
        .all()
    )
    by_account = {row.account_id: row for row in existing}

    for entry in data.entries:
        row = by_account.get(entry.account_id)
        if row:
            row.balance = entry.balance
        else:
            db.add(
                WealthSnapshot(
                    user_id=current_user_id,
                    account_id=entry.account_id,
                    balance=entry.balance,
                    snapshot_date=snapshot_date,
                )
            )

    db.commit()
    return {"date": snapshot_date, "saved": len(data.entries)}


# ─── Overview ─────────────────────────────────────────────────────────────────

@router.get("/overview")
def get_overview(
    months: int = DEFAULT_MONTHS,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    months = max(1, min(MAX_MONTHS, int(months)))
    start = _month_start(months - 1)

    accounts = _active_accounts(db, current_user_id)
    account_ids = [account.id for account in accounts]
    all_rows = _all_snapshots(db, current_user_id, account_ids)

    # Serie storica: somma dei saldi per data (solo conti attivi, finestra `months`).
    series_map: dict[str, float] = defaultdict(float)
    for row in all_rows:
        if row.snapshot_date >= start:
            series_map[row.snapshot_date] += row.balance
    series = [
        {"date": day, "total": round(total, 2)}
        for day, total in sorted(series_map.items())
    ]

    current = series[-1] if series else None
    previous = series[-2] if len(series) > 1 else None
    delta = (
        round(current["total"] - previous["total"], 2)
        if current and previous
        else None
    )
    delta_pct = (
        round(delta / previous["total"] * 100, 2)
        if delta is not None and previous["total"]
        else None
    )

    # Ultimo saldo noto per conto: non limitato alla finestra, altrimenti un conto
    # aggiornato prima della finestra sparirebbe dalla fotografia attuale.
    history_by_account: dict[int, list[WealthSnapshot]] = defaultdict(list)
    for row in all_rows:
        history_by_account[row.account_id].append(row)

    kind_totals: dict[str, float] = defaultdict(float)
    accounts_out = []
    for account in accounts:
        history = history_by_account.get(account.id, [])
        last = history[-1] if history else None
        balance = last.balance if last else 0.0
        if last:
            kind_totals[account.kind] += last.balance
        account_delta = (
            round(history[-1].balance - history[-2].balance, 2)
            if len(history) >= 2
            else None
        )
        accounts_out.append(
            {
                "id": account.id,
                "name": account.name,
                "kind": account.kind,
                "balance": round(balance, 2),
                "delta": account_delta,
                "last_date": last.snapshot_date if last else None,
            }
        )

    composition_total = sum(kind_totals.values())
    composition = [
        {
            "kind": kind,
            "total": round(total, 2),
            "pct": round(total / composition_total * 100, 1)
            if composition_total
            else 0.0,
        }
        for kind, total in sorted(
            kind_totals.items(), key=lambda item: item[1], reverse=True
        )
    ]

    return {
        "series": series,
        "current": current,
        "previous": previous,
        "delta": delta,
        "delta_pct": delta_pct,
        "composition": composition,
        "accounts": accounts_out,
    }


@router.get("/accounts/{account_id}/history")
def account_history(
    account_id: int,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    account = _account_or_404(db, account_id, current_user_id)
    rows = (
        db.query(WealthSnapshot)
        .filter(
            WealthSnapshot.user_id == current_user_id,
            WealthSnapshot.account_id == account_id,
        )
        .order_by(WealthSnapshot.snapshot_date.asc(), WealthSnapshot.id.asc())
        .all()
    )
    return {
        "account": {"id": account.id, "name": account.name, "kind": account.kind},
        "history": [
            {"date": row.snapshot_date, "balance": round(row.balance, 2)}
            for row in rows
        ],
    }
