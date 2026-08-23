from __future__ import annotations

import base64
import io
import json
import os
from calendar import monthrange
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.core.database import get_db, Transaction, Budget
from backend.api.auth import get_current_user

router = APIRouter(prefix="/api/v1/report", tags=["report"])

# ── Groq client (same as ai_engine) ─────────────────────────────────────────
from openai import OpenAI as _OpenAI

_groq = _OpenAI(
    api_key=os.getenv("GROQ_API_KEY", ""),
    base_url="https://api.groq.com/openai/v1",
)

REPORT_NARRATIVE_PROMPT = """\
Sei FinCopilot. Genera una narrativa di analisi finanziaria per il report mensile di {month_label}.

DATI:
- Totale spese: €{total_month} ({delta_pct:+.1f}% vs mese precedente €{total_prev})
- Transazioni: {count_month} (media €{avg_tx} per transazione)
- Categoria principale: {top_category} (€{top_cat_amount}, {top_cat_pct:.0f}% del totale)
- Categorie con budget sforato: {over_budget_cats}

Scrivi 3 paragrafi in italiano:
1. PANORAMICA (2-3 frasi): andamento generale del mese, confronto col precedente, tono oggettivo
2. PUNTI DI ATTENZIONE (2-3 frasi): categorie che pesano di più, eventuali sforamenti budget, cosa è cambiato
3. RACCOMANDAZIONE (1-2 frasi): un'azione concreta e specifica per il mese successivo basata sui dati

Stile: professionale ma diretto. Usa cifre esatte. No elenchi puntati.
Rispondi con JSON: {{"panoramica": "...", "attenzione": "...", "raccomandazione": "..."}}"""

MONTH_LABELS_IT = [
    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
    "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre",
]


def _fmt_eur(v: float) -> str:
    """Italian number format: 1.842,50"""
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _esc(s) -> str:
    """Escape minimo per inserire testo utente/AI dentro l'HTML del report."""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _bar_html(pct: float, fill_hex: str, track_hex: str, width_px: int = 130, height_px: int = 8) -> str:
    """Barra di progresso come tabella a due celle (niente div annidate: xhtml2pdf le tratta
    come blocchi impilati verticalmente invece che sovrapposti/affiancati — le tabelle invece
    rispettano le larghezze di colonna in modo affidabile, verificato empiricamente)."""
    width_px = max(width_px, 1)
    fill_w = round(width_px * min(max(pct, 0.0), 100.0) / 100.0)
    rest_w = width_px - fill_w
    cells = ""
    if fill_w > 0:
        cells += (
            f'<td style="width:{fill_w}px; height:{height_px}px; background-color:{fill_hex}; '
            f'padding:0; font-size:1px; line-height:1px;">&nbsp;</td>'
        )
    if rest_w > 0:
        cells += (
            f'<td style="width:{rest_w}px; height:{height_px}px; background-color:{track_hex}; '
            f'padding:0; font-size:1px; line-height:1px;">&nbsp;</td>'
        )
    return f'<table style="width:{width_px}px; border-collapse:collapse;"><tr>{cells}</tr></table>'


def _build_narrative(data: dict) -> dict:
    try:
        prompt = REPORT_NARRATIVE_PROMPT.format(**data)
        resp = _groq.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
            seed=42,
            reasoning_effort="none",
        )
        raw = resp.choices[0].message.content.strip()
        # strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(raw)
    except Exception:
        return {
            "panoramica": f"Report generato per {data['month_label']}.",
            "attenzione": "Consulta i dettagli nelle sezioni sottostanti.",
            "raccomandazione": "Analizza le categorie con maggiore incidenza.",
        }


# ── Palette report — stessi token del design system frontend (base.css), adattati per
# la stampa su sfondo chiaro: gli sfondi scuri "a pagina intera" non sono affidabili nel
# motore di rendering HTML→PDF usato (xhtml2pdf renderizza correttamente gli sfondi sui
# singoli blocchi/card, ma non su tutta l'altezza pagina) — vedi test in sviluppo. I toni
# status (success/warning/danger) sono scuriti rispetto alle versioni pastello dell'app,
# pensate per un tema scuro, per restare leggibili su bianco.
ACCENT       = "#d9663f"   # --accent
ACCENT_TINT  = "#fbeee7"   # tint leggero dell'accent, per il box Raccomandazione
INK          = "#1a1a1c"   # testo principale (spirito di --navy-0 su sfondo chiaro)
INK_MUTED    = "#6b6b72"   # --text-muted, adattato
INK_DIM      = "#97979e"   # --text-dim, adattato
BORDER       = "#e6e6ea"   # --glass-border, versione chiara
CARD_BG      = "#f7f7f9"   # --surface-container, versione chiara
HEADER_BG    = "#17171a"   # --navy-1 — unico blocco scuro, delimitato (safe da renderizzare)
SUCCESS      = "#2f8f5b"   # --success, scurito per contrasto su bianco
WARNING      = "#b9822c"   # --warning, scurito
DANGER       = "#c14a42"   # --danger, scurito
RADIUS_MD    = "10px"
RADIUS_LG    = "14px"


def _section_html(title: str) -> str:
    return (
        f'<table style="width:100%; margin-top:16px; margin-bottom:8px;"><tr>'
        f'<td style="width:4px; background-color:{ACCENT}; border-radius:2px;">&nbsp;</td>'
        f'<td style="padding-left:8px; font-size:12.5pt; font-weight:bold; color:{INK};">{_esc(title)}</td>'
        f'</tr></table>'
    )


def _kpi_card_html(label: str, value: str, value_color: str = INK) -> str:
    return (
        f'<td style="width:25%; padding:4px;">'
        f'<div style="background-color:{CARD_BG}; border:1px solid {BORDER}; border-radius:{RADIUS_MD}; padding:10px 12px;">'
        f'<div style="font-size:8pt; color:{INK_MUTED}; text-transform:uppercase;">{_esc(label)}</div>'
        f'<div style="font-size:15pt; font-weight:bold; color:{value_color}; margin-top:2px;">{_esc(value)}</div>'
        f'</div></td>'
    )


def _table_html(headers: list, rows: list, col_widths: list, align: Optional[list] = None) -> str:
    """Tabella con lo stesso linguaggio visivo delle tabelle dell'app: header scuro,
    righe alternate chiaro/off-white, bordo sottile. `rows` è già una lista di celle HTML
    pronte (stringhe), non testo grezzo — chi chiama gestisce l'escaping dov'è testo utente."""
    align = align or ["left"] * len(headers)
    head_cells = "".join(
        f'<th style="width:{w}; text-align:{a}; padding:7px 8px; background-color:{HEADER_BG}; '
        f'color:#fff; font-size:8.5pt; font-weight:bold; border:1px solid {HEADER_BG};">{_esc(h)}</th>'
        for h, w, a in zip(headers, col_widths, align)
    )
    body_rows = []
    for i, row in enumerate(rows):
        bg = "#ffffff" if i % 2 == 0 else CARD_BG
        cells = "".join(
            f'<td style="text-align:{a}; padding:6px 8px; font-size:8.5pt; color:{INK}; '
            f'border:1px solid {BORDER}; background-color:{bg};">{cell}</td>'
            for cell, a in zip(row, align)
        )
        body_rows.append(f"<tr>{cells}</tr>")
    return (
        f'<table style="width:100%; border-collapse:collapse; margin-top:2px;">'
        f'<tr>{head_cells}</tr>{"".join(body_rows)}</table>'
    )


def _build_pdf(
    year: int,
    month: int,
    month_label: str,
    total_month: float,
    total_prev: float,
    count_month: int,
    avg_tx: float,
    delta_pct: float,
    categories: list,
    top10: list,
    budget_rows: list,
    narrative: dict,
) -> bytes:
    from xhtml2pdf import pisa

    generated_on = date.today().strftime("%d/%m/%Y")

    base_css = f"""
        @page {{ size: A4; margin: 1.8cm; }}
        body {{ font-family: Helvetica, Arial, sans-serif; color: {INK}; font-size: 9.5pt; }}
        p {{ line-height: 1.5; margin: 0; }}
    """

    header_html = (
        f'<table style="width:100%; background-color:{HEADER_BG}; border-radius:{RADIUS_LG};">'
        f'<tr><td style="padding:16px 18px;">'
        f'<span style="font-size:16pt; font-weight:bold; color:{ACCENT};">FinCopilot</span>'
        f'<span style="font-size:11pt; color:#ffffff;"> &nbsp;Report Mensile</span><br/>'
        f'<span style="font-size:12.5pt; color:#ffffff; font-weight:bold;">{_esc(month_label)}</span><br/>'
        f'<span style="font-size:8pt; color:{INK_DIM};">Generato il {generated_on}</span>'
        f'</td></tr></table>'
    )

    if count_month == 0:
        html = f"""<html><head><style>{base_css}</style></head><body>
            {header_html}
            <p style="margin-top:24px; color:{INK_MUTED};">Nessuna transazione registrata per questo mese.</p>
        </body></html>"""
        buf = io.BytesIO()
        pisa.CreatePDF(html, dest=buf)
        return buf.getvalue()

    # ── KPI ─────────────────────────────────────────────────────────────────
    if total_prev > 0:
        delta_str = f"{delta_pct:+.1f}%"
        delta_color = SUCCESS if delta_pct <= 0 else DANGER  # meno speso = verde, di più = rosso
    else:
        delta_str, delta_color = "n/d", INK
    kpi_html = (
        '<table style="width:100%; margin-top:10px;"><tr>'
        + _kpi_card_html("Totale spese", f"€{_fmt_eur(total_month)}")
        + _kpi_card_html("Transazioni", str(count_month))
        + _kpi_card_html("Media/transazione", f"€{_fmt_eur(avg_tx)}")
        + _kpi_card_html("Vs mese precedente", delta_str, delta_color)
        + "</tr></table>"
    )

    # ── SPESE PER CATEGORIA ──────────────────────────────────────────────────
    cat_rows = [
        [
            _esc(c["category"]),
            f"€{_fmt_eur(c['total'])}",
            f"{c['pct']:.1f}%",
            _bar_html(c["pct"], ACCENT, BORDER),
            str(c["count"]),
        ]
        for c in categories
    ]
    cat_table_html = _table_html(
        ["Categoria", "Importo", "%", "Distribuzione", "N°"],
        cat_rows,
        ["18%", "16%", "10%", "42%", "10%"],
        ["left", "right", "right", "left", "center"],
    )

    # ── BUDGET STATUS ────────────────────────────────────────────────────────
    budget_html = ""
    if budget_rows:
        bud_rows = []
        for b in budget_rows:
            pct = b["pct"]
            if pct < 80:
                stato, stato_color = "OK", SUCCESS
            elif pct <= 100:
                stato, stato_color = "ATTENZIONE", WARNING
            else:
                stato, stato_color = "SFORATO", DANGER
            bud_rows.append([
                _esc(b["category"]),
                f"€{_fmt_eur(b['budget'])}",
                f"€{_fmt_eur(b['spent'])}",
                f'<span style="color:{stato_color}; font-weight:bold;">{pct:.0f}%</span>',
                f'<span style="color:{stato_color}; font-weight:bold;">{stato}</span>',
            ])
        budget_html = _section_html("Budget Status") + _table_html(
            ["Categoria", "Budget", "Speso", "%", "Stato"],
            bud_rows,
            ["22%", "18%", "18%", "16%", "26%"],
            ["left", "right", "right", "center", "center"],
        )

    # ── TOP 10 ───────────────────────────────────────────────────────────────
    top_rows = [
        [
            t["date"],
            _esc(t["category"]),
            _esc((t["description"] or "—")[:45]),
            f"€{_fmt_eur(t['amount'])}",
        ]
        for t in top10
    ]
    top_table_html = _table_html(
        ["Data", "Categoria", "Descrizione", "Importo"],
        top_rows,
        ["14%", "18%", "48%", "20%"],
        ["left", "left", "left", "right"],
    )

    html = f"""<html><head><style>{base_css}</style></head><body>
        {header_html}

        {_section_html("Panoramica del mese")}
        <p>{_esc(narrative["panoramica"])}</p>

        {_section_html("KPI principali")}
        {kpi_html}

        {_section_html("Spese per categoria")}
        {cat_table_html}

        {_section_html("Punti di attenzione")}
        <p>{_esc(narrative["attenzione"])}</p>

        {budget_html}

        {_section_html("Top 10 transazioni")}
        {top_table_html}

        {_section_html("Raccomandazione")}
        <table style="width:100%;"><tr>
          <td style="background-color:{ACCENT_TINT}; border-left:3px solid {ACCENT}; border-radius:{RADIUS_MD}; padding:10px 14px;">
            <p>{_esc(narrative["raccomandazione"])}</p>
          </td>
        </tr></table>

        <p style="margin-top:20px; font-size:7.5pt; color:{INK_DIM}; text-align:center;">
          Generato automaticamente da FinCopilot · Dati aggiornati al momento della generazione
        </p>
    </body></html>"""

    buf = io.BytesIO()
    result = pisa.CreatePDF(html, dest=buf)
    if result.err:
        raise RuntimeError(f"Errore generazione PDF ({result.err} errori di rendering)")
    return buf.getvalue()


@router.get("/monthly")
async def monthly_report(
    year:  Optional[int] = None,
    month: Optional[int] = None,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    today = date.today()
    if year is None:
        year = today.year if today.month > 1 else today.year - 1
    if month is None:
        month = today.month - 1 if today.month > 1 else 12

    month = max(1, min(12, month))

    first_day = date(year, month, 1)
    last_day  = date(year, month, monthrange(year, month)[1])

    if month == 1:
        prev_first = date(year - 1, 12, 1)
        prev_last  = date(year - 1, 12, 31)
    else:
        prev_first = date(year, month - 1, 1)
        prev_last  = date(year, month - 1, monthrange(year, month - 1)[1])

    fd = first_day.isoformat()
    ld = last_day.isoformat()
    pf = prev_first.isoformat()
    pl = prev_last.isoformat()

    # ── BLOCCO A — totali ────────────────────────────────────────────────────
    row = db.query(
        func.coalesce(func.sum(Transaction.amount), 0.0),
        func.count(Transaction.id),
    ).filter(
        (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
    ).one()
    total_month = round(float(row[0]), 2)
    count_month = int(row[1])
    avg_tx = round(total_month / count_month, 2) if count_month else 0.0

    prev_row = db.query(
        func.coalesce(func.sum(Transaction.amount), 0.0),
    ).filter(
        (Transaction.date >= pf) & (Transaction.date <= pl) & (Transaction.user_id == current_user_id)
    ).scalar()
    total_prev = round(float(prev_row), 2)

    if total_prev > 0:
        delta_pct = round((total_month - total_prev) / total_prev * 100, 1)
    else:
        delta_pct = 0.0

    # ── BLOCCO B — categorie ─────────────────────────────────────────────────
    cat_rows = (
        db.query(Transaction.category, func.sum(Transaction.amount), func.count(Transaction.id))
        .filter(
            (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .all()
    )
    categories = [
        {
            "category": r[0],
            "total": round(float(r[1]), 2),
            "count": int(r[2]),
            "pct": round(float(r[1]) / total_month * 100, 1) if total_month else 0.0,
        }
        for r in cat_rows
    ]

    # ── BLOCCO C — top 10 ────────────────────────────────────────────────────
    top_txs = (
        db.query(Transaction)
        .filter(
            (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
        )
        .order_by(Transaction.amount.desc())
        .limit(10)
        .all()
    )
    top10 = [
        {"date": t.date, "category": t.category, "description": t.description, "amount": round(t.amount, 2)}
        for t in top_txs
    ]

    # ── BLOCCO D — budget ────────────────────────────────────────────────────
    budgets = db.query(Budget).filter(
        (Budget.active == True) & (Budget.user_id == current_user_id)
    ).all()
    budget_rows = []
    for b in budgets:
        spent_row = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            (Transaction.category == b.category) &
            (Transaction.date >= fd) &
            (Transaction.date <= ld) &
            (Transaction.user_id == current_user_id),
        ).scalar()
        spent = round(float(spent_row), 2)
        pct = round(spent / b.amount * 100, 1) if b.amount else 0.0
        budget_rows.append({"category": b.category, "budget": b.amount, "spent": spent, "pct": pct})
    budget_rows.sort(key=lambda x: x["pct"], reverse=True)

    # ── NARRATIVA AI ─────────────────────────────────────────────────────────
    top_cat   = categories[0] if categories else {"category": "n/d", "total": 0.0, "pct": 0.0}
    over_cats = [b["category"] for b in budget_rows if b["pct"] > 100]
    month_label = f"{MONTH_LABELS_IT[month]} {year}"

    narrative = _build_narrative({
        "month_label":    month_label,
        "total_month":    _fmt_eur(total_month),
        "total_prev":     _fmt_eur(total_prev),
        "delta_pct":      delta_pct,
        "count_month":    count_month,
        "avg_tx":         _fmt_eur(avg_tx),
        "top_category":   top_cat["category"],
        "top_cat_amount": _fmt_eur(top_cat["total"]),
        "top_cat_pct":    top_cat["pct"],
        "over_budget_cats": ", ".join(over_cats) if over_cats else "nessuna",
    })

    # ── GENERA PDF ───────────────────────────────────────────────────────────
    pdf_bytes = _build_pdf(
        year=year, month=month, month_label=month_label,
        total_month=total_month, total_prev=total_prev,
        count_month=count_month, avg_tx=avg_tx, delta_pct=delta_pct,
        categories=categories, top10=top10,
        budget_rows=budget_rows,
        narrative=narrative,
    )

    filename = f"fincopilot_report_{year}_{month:02d}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/monthly/generate")
async def generate_monthly_report(
    year: int,
    month: int,
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera report mensile on-demand.
    """
    try:
        # Valida year/month
        if month < 1 or month > 12 or year < 2000:
            raise HTTPException(400, "Invalid year/month")

        # STEP 1: Raccogli dati transazioni
        first_day = date(year, month, 1)
        last_day = date(year, month, monthrange(year, month)[1])

        if month == 1:
            prev_first = date(year - 1, 12, 1)
            prev_last = date(year - 1, 12, 31)
        else:
            prev_first = date(year, month - 1, 1)
            prev_last = date(year, month - 1, monthrange(year, month - 1)[1])

        fd = first_day.isoformat()
        ld = last_day.isoformat()
        pf = prev_first.isoformat()
        pl = prev_last.isoformat()

        # Totali
        row = db.query(
            func.coalesce(func.sum(Transaction.amount), 0.0),
            func.count(Transaction.id),
        ).filter(
            (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
        ).one()
        total_month = round(float(row[0]), 2)
        count_month = int(row[1])
        avg_tx = round(total_month / count_month, 2) if count_month else 0.0

        prev_row = db.query(
            func.coalesce(func.sum(Transaction.amount), 0.0),
        ).filter(
            (Transaction.date >= pf) & (Transaction.date <= pl) & (Transaction.user_id == current_user_id)
        ).scalar()
        total_prev = round(float(prev_row), 2)

        delta_pct = round((total_month - total_prev) / total_prev * 100, 1) if total_prev > 0 else 0.0

        # Categorie
        cat_rows = (
            db.query(Transaction.category, func.sum(Transaction.amount), func.count(Transaction.id))
            .filter(
                (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
            )
            .group_by(Transaction.category)
            .order_by(func.sum(Transaction.amount).desc())
            .all()
        )
        categories = [
            {
                "category": r[0],
                "total": round(float(r[1]), 2),
                "count": int(r[2]),
                "pct": round(float(r[1]) / total_month * 100, 1) if total_month else 0.0,
            }
            for r in cat_rows
        ]

        # Top 10
        top_txs = (
            db.query(Transaction)
            .filter(
                (Transaction.date >= fd) & (Transaction.date <= ld) & (Transaction.user_id == current_user_id)
            )
            .order_by(Transaction.amount.desc())
            .limit(10)
            .all()
        )
        top10 = [
            {"date": t.date, "category": t.category, "description": t.description, "amount": round(t.amount, 2)}
            for t in top_txs
        ]

        # Budget
        budgets = db.query(Budget).filter(
            (Budget.active == True) & (Budget.user_id == current_user_id)
        ).all()
        budget_rows = []
        for b in budgets:
            spent_row = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
                (Transaction.category == b.category) &
                (Transaction.date >= fd) &
                (Transaction.date <= ld) &
                (Transaction.user_id == current_user_id),
            ).scalar()
            spent = round(float(spent_row), 2)
            pct = round(spent / b.amount * 100, 1) if b.amount else 0.0
            budget_rows.append({"category": b.category, "budget": b.amount, "spent": spent, "pct": pct})
        budget_rows.sort(key=lambda x: x["pct"], reverse=True)

        # Narrativa
        top_cat = categories[0] if categories else {"category": "n/d", "total": 0.0, "pct": 0.0}
        over_cats = [b["category"] for b in budget_rows if b["pct"] > 100]
        month_label = f"{MONTH_LABELS_IT[month]} {year}"

        narrative = _build_narrative({
            "month_label": month_label,
            "total_month": _fmt_eur(total_month),
            "total_prev": _fmt_eur(total_prev),
            "delta_pct": delta_pct,
            "count_month": count_month,
            "avg_tx": _fmt_eur(avg_tx),
            "top_category": top_cat["category"],
            "top_cat_amount": _fmt_eur(top_cat["total"]),
            "top_cat_pct": top_cat["pct"],
            "over_budget_cats": ", ".join(over_cats) if over_cats else "nessuna",
        })

        # STEP 2: Genera PDF
        pdf_bytes = _build_pdf(
            year=year, month=month, month_label=month_label,
            total_month=total_month, total_prev=total_prev,
            count_month=count_month, avg_tx=avg_tx, delta_pct=delta_pct,
            categories=categories, top10=top10,
            budget_rows=budget_rows,
            narrative=narrative,
        )

        filename = f"fincopilot_report_{year}_{month:02d}.pdf"
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        return {
            "status": "success",
            "filename": filename,
            "size_kb": len(pdf_bytes) / 1024,
            "pdf_base64": pdf_base64,
        }
    except Exception as e:
        raise HTTPException(500, f"Errore generazione report: {str(e)}")

