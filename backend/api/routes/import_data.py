from __future__ import annotations
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.core.database import get_db, Transaction
from backend.core.import_engine import (
    parse_upload, suggest_mapping, normalize_row, categorize_batch,
    split_expenses_and_income, ImportError_, TARGET_FIELDS, REQUIRED_FIELDS, PREVIEW_ROWS,
)
from backend.core.ai_engine import invalidate_anomaly_cache
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/transactions/import", tags=["import"])


@router.post("/preview")
async def preview_import(
    file: UploadFile = File(...),
    current_user_id: str = Depends(get_current_user),
):
    """Legge il file caricato (CSV/XLSX), propone un mapping colonne→campi (AI +
    euristica) e ritorna un'anteprima. Non scrive nulla sul DB."""
    content = await file.read()
    try:
        df = parse_upload(file.filename or "", content)
    except ImportError_ as e:
        raise HTTPException(400, str(e))

    columns = list(df.columns)
    preview_rows = df.head(PREVIEW_ROWS).to_dict(orient="records")
    mapping = suggest_mapping(columns, preview_rows)

    return {
        "columns": columns,
        "preview_rows": preview_rows,
        "suggested_mapping": mapping,
        "target_fields": TARGET_FIELDS,
        "required_fields": REQUIRED_FIELDS,
        "total_rows": len(df),
    }


@router.post("/commit")
async def commit_import(
    file: UploadFile = File(...),
    mapping: str = Form(...),  # JSON string: {"date": "colX", "amount": "colY", ...}
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Riceve di nuovo il file + il mapping confermato dall'utente, normalizza tutte
    le righe, deduplica contro le transazioni esistenti, categorizza con AI le righe
    senza categoria mappata e importa quelle valide."""
    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(400, "Mapping non valido")

    for field in REQUIRED_FIELDS:
        if not mapping_dict.get(field):
            raise HTTPException(400, f"Campo obbligatorio non mappato: {field}")

    content = await file.read()
    try:
        df = parse_upload(file.filename or "", content)
    except ImportError_ as e:
        raise HTTPException(400, str(e))

    raw_rows = df.to_dict(orient="records")
    normalized: list[dict] = []
    invalid_count = 0
    for row in raw_rows:
        n = normalize_row(row, mapping_dict)
        if n is None:
            invalid_count += 1
        else:
            normalized.append(n)

    if not normalized:
        raise HTTPException(400, "Nessuna riga valida da importare (controlla il mapping di data/importo)")

    # FinCopilot traccia solo spese: scarta le entrate se il file mescola i segni
    normalized, skipped_income = split_expenses_and_income(normalized)
    if not normalized:
        return {
            "imported": 0,
            "skipped_duplicates": 0,
            "skipped_income": skipped_income,
            "invalid_rows": invalid_count,
        }

    # Dedup contro le transazioni esistenti dell'utente su (date, amount, description) — T-002
    existing = db.query(Transaction.date, Transaction.amount, Transaction.description).filter(
        Transaction.user_id == current_user_id
    ).all()
    existing_keys = {(d, round(a, 2), (desc or "").strip()) for d, a, desc in existing}

    to_import: list[dict] = []
    skipped_duplicates = 0
    for n in normalized:
        key = (n["date"], n["amount"], n["description"])
        if key in existing_keys:
            skipped_duplicates += 1
            continue
        to_import.append(n)
        existing_keys.add(key)  # evita doppi anche tra righe duplicate nello stesso file

    if not to_import:
        return {
            "imported": 0,
            "skipped_duplicates": skipped_duplicates,
            "skipped_income": skipped_income,
            "invalid_rows": invalid_count,
        }

    # Categorizzazione AI in batch per le righe senza categoria dal mapping (T-003)
    needs_category_idx = [i for i, n in enumerate(to_import) if not n["category"]]
    if needs_category_idx:
        descriptions = [to_import[i]["description"] for i in needs_category_idx]
        ai_categories = categorize_batch(descriptions)
        for idx, cat in zip(needs_category_idx, ai_categories):
            to_import[idx]["category"] = cat

    touched_months: set[tuple[int, int]] = set()
    for n in to_import:
        tx = Transaction(
            user_id=current_user_id,
            amount=n["amount"],
            category=n["category"] or "altro",
            description=n["description"],
            date=n["date"],
            account=n["account"],
            source="import",
        )
        db.add(tx)
        y, m = n["date"][:4], n["date"][5:7]
        touched_months.add((int(y), int(m)))

    db.commit()

    for year, month in touched_months:
        try:
            invalidate_anomaly_cache(current_user_id, year, month)
        except Exception:
            pass

    return {
        "imported": len(to_import),
        "skipped_duplicates": skipped_duplicates,
        "skipped_income": skipped_income,
        "invalid_rows": invalid_count,
    }
