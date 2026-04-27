from __future__ import annotations

import io
import json
import os
from calendar import monthrange
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.core.database import get_db, Transaction, Budget

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
- Anomalie rilevate: {anomaly_count}

Scrivi 3 paragrafi in italiano:
1. PANORAMICA (2-3 frasi): andamento generale del mese, confronto col precedente, tono oggettivo
2. PUNTI DI ATTENZIONE (2-3 frasi): categorie che pesano di più, eventuali anomalie o sforamenti budget, cosa è cambiato
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


def _progress_bar(pct: float, fill_hex: str, bar_width: float = 110, bar_height: float = 9):
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.lib import colors as _c
    d = Drawing(bar_width, bar_height)
    d.add(Rect(0, 0, bar_width, bar_height,
               fillColor=_c.HexColor("#E0E0E0"), strokeColor=None))
    fill_w = bar_width * min(pct, 100.0) / 100.0
    if fill_w > 0:
        d.add(Rect(0, 0, fill_w, bar_height,
                   fillColor=_c.HexColor(fill_hex), strokeColor=None))
    return d


def _build_narrative(data: dict) -> dict:
    try:
        prompt = REPORT_NARRATIVE_PROMPT.format(**data)
        resp = _groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=600,
            seed=42,
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
    anomalies: list,
    narrative: dict,
) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    PRIMARY = colors.HexColor("#FF8C42")
    DARK    = colors.HexColor("#1A1A1A")
    MUTED   = colors.HexColor("#888888")
    SUCCESS = colors.HexColor("#00C878")
    WARNING = colors.HexColor("#FFB347")
    DANGER  = colors.HexColor("#FF4D6D")
    BG_ROW  = colors.HexColor("#F5F5F5")
    WHITE   = colors.white

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], textColor=PRIMARY, fontSize=20, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=DARK, fontSize=13, spaceBefore=14, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=15, textColor=DARK)
    meta = ParagraphStyle("meta", parent=styles["Normal"], fontSize=9, textColor=MUTED)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, textColor=MUTED, alignment=1)

    def section(title: str) -> list:
        return [
            Spacer(1, 0.3 * cm),
            HRFlowable(width="100%", thickness=1, color=PRIMARY, spaceAfter=4),
            Paragraph(title, h2),
        ]

    def tbl(data: list, col_widths: list, header_bg=PRIMARY) -> Table:
        t = Table(data, colWidths=col_widths)
        n = len(data)
        style_cmds = [
            ("BACKGROUND",  (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
            ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",    (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_ROW]),
            ("GRID",        (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("LEFTPADDING",  (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING",   (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ]
        t.setStyle(TableStyle(style_cmds))
        return t

    story = []

    # ── HEADER ──────────────────────────────────────────────────────────────
    story.append(Paragraph("FinCopilot — Report Mensile", h1))
    story.append(Paragraph(month_label, ParagraphStyle("sub", fontSize=14, textColor=DARK, spaceAfter=2)))
    story.append(Paragraph(f"Generato il: {date.today().strftime('%d/%m/%Y')}", meta))
    story.append(Spacer(1, 0.4 * cm))

    if count_month == 0:
        story.append(Paragraph("Nessuna transazione registrata per questo mese.", body))
        doc.build(story)
        return buf.getvalue()

    # ── PANORAMICA ───────────────────────────────────────────────────────────
    story += section("Panoramica del Mese")
    story.append(Paragraph(narrative["panoramica"], body))

    # ── KPI ─────────────────────────────────────────────────────────────────
    story += section("KPI Principali")
    delta_str = f"{delta_pct:+.1f}%" if total_prev > 0 else "n/d"
    kpi_data = [
        ["Totale Spese", "Transazioni", "Media/Transazione", "Vs Mese Prec."],
        [
            f"€{_fmt_eur(total_month)}",
            str(count_month),
            f"€{_fmt_eur(avg_tx)}",
            delta_str,
        ],
    ]
    page_w = A4[0] - 4 * cm
    story.append(tbl(kpi_data, [page_w / 4] * 4))

    # ── SPESE PER CATEGORIA ──────────────────────────────────────────────────
    story += section("Spese per Categoria")
    cat_header = ["Categoria", "Importo (€)", "%", "Distribuzione", "N°"]
    cat_rows = [cat_header]
    for c in categories:
        cat_rows.append([
            c["category"],
            f"{c['total']:.2f}",
            f"{c['pct']:.1f}%",
            _progress_bar(c["pct"], "#FF8C42"),
            str(c["count"]),
        ])
    story.append(tbl(cat_rows, [3.5 * cm, 2.5 * cm, 1.5 * cm, 5.8 * cm, 1.2 * cm]))

    # ── PUNTI DI ATTENZIONE ──────────────────────────────────────────────────
    story += section("Punti di Attenzione")
    story.append(Paragraph(narrative["attenzione"], body))

    # ── BUDGET STATUS ────────────────────────────────────────────────────────
    if budget_rows:
        story += section("Budget Status")
        bud_header = ["Categoria", "Budget (€)", "Speso (€)", "%", "Stato"]
        bud_data = [bud_header]
        for b in budget_rows:
            pct = b["pct"]
            stato = "OK" if pct < 80 else ("ATTENZIONE" if pct <= 100 else "SFORATO")
            bud_data.append([
                b["category"],
                f"{b['budget']:.2f}",
                f"{b['spent']:.2f}",
                f"{pct:.0f}%",
                stato,
            ])
        bt = tbl(bud_data, [3.5 * cm, 2.5 * cm, 2.5 * cm, 1.5 * cm, 2.5 * cm])
        # Color the % column per status
        for row_idx, b in enumerate(budget_rows, start=1):
            pct = b["pct"]
            col_color = SUCCESS if pct < 80 else (WARNING if pct <= 100 else DANGER)
            bt.setStyle(TableStyle([
                ("TEXTCOLOR", (3, row_idx), (4, row_idx), col_color),
                ("FONTNAME",  (3, row_idx), (4, row_idx), "Helvetica-Bold"),
            ]))
        story.append(bt)

    # ── TOP 10 ───────────────────────────────────────────────────────────────
    story += section("Top 10 Transazioni")
    top_header = ["Data", "Categoria", "Descrizione", "Importo (€)"]
    top_data = [top_header]
    for t in top10:
        top_data.append([
            t["date"],
            t["category"],
            (t["description"] or "—")[:40],
            f"{t['amount']:.2f}",
        ])
    story.append(tbl(top_data, [2 * cm, 3 * cm, 7.5 * cm, 2.5 * cm]))

    # ── ANOMALIE ─────────────────────────────────────────────────────────────
    if anomalies:
        story += section("Anomalie Rilevate")
        an_header = ["Data", "Categoria", "Descrizione", "Importo (€)", "Z-score"]
        an_data = [an_header]
        for a in anomalies:
            an_data.append([
                a["date"],
                a["category"],
                (a["description"] or "—")[:35],
                f"{a['amount']:.2f}",
                f"{a.get('z_score', 0):.1f}",
            ])
        story.append(tbl(an_data, [2 * cm, 2.5 * cm, 6 * cm, 2.5 * cm, 2 * cm]))

    # ── RACCOMANDAZIONE ──────────────────────────────────────────────────────
    story += section("Raccomandazione")
    story.append(Paragraph(narrative["raccomandazione"], body))

    # ── FOOTER NOTE ─────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Generato automaticamente da FinCopilot · Dati aggiornati al momento della generazione", small))

    doc.build(story)
    return buf.getvalue()


@router.get("/monthly")
async def monthly_report(
    year:  Optional[int] = None,
    month: Optional[int] = None,
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
    ).filter(Transaction.date >= fd, Transaction.date <= ld).one()
    total_month = round(float(row[0]), 2)
    count_month = int(row[1])
    avg_tx = round(total_month / count_month, 2) if count_month else 0.0

    prev_row = db.query(
        func.coalesce(func.sum(Transaction.amount), 0.0),
    ).filter(Transaction.date >= pf, Transaction.date <= pl).scalar()
    total_prev = round(float(prev_row), 2)

    if total_prev > 0:
        delta_pct = round((total_month - total_prev) / total_prev * 100, 1)
    else:
        delta_pct = 0.0

    # ── BLOCCO B — categorie ─────────────────────────────────────────────────
    cat_rows = (
        db.query(Transaction.category, func.sum(Transaction.amount), func.count(Transaction.id))
        .filter(Transaction.date >= fd, Transaction.date <= ld)
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
        .filter(Transaction.date >= fd, Transaction.date <= ld)
        .order_by(Transaction.amount.desc())
        .limit(10)
        .all()
    )
    top10 = [
        {"date": t.date, "category": t.category, "description": t.description, "amount": round(t.amount, 2)}
        for t in top_txs
    ]

    # ── BLOCCO D — budget ────────────────────────────────────────────────────
    budgets = db.query(Budget).filter(Budget.active == True).all()
    budget_rows = []
    for b in budgets:
        spent_row = db.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            Transaction.category == b.category,
            Transaction.date >= fd,
            Transaction.date <= ld,
        ).scalar()
        spent = round(float(spent_row), 2)
        pct = round(spent / b.amount * 100, 1) if b.amount else 0.0
        budget_rows.append({"category": b.category, "budget": b.amount, "spent": spent, "pct": pct})
    budget_rows.sort(key=lambda x: x["pct"], reverse=True)

    # ── BLOCCO E — anomalie (filtrate al mese) ───────────────────────────────
    try:
        from backend.core.ai_engine import get_anomalies as _get_anomalies
        all_anomalies = _get_anomalies()
        anomalies = [a for a in all_anomalies if fd <= a.get("date", "") <= ld][:5]
    except Exception:
        anomalies = []

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
        "anomaly_count":  len(anomalies),
    })

    # ── GENERA PDF ───────────────────────────────────────────────────────────
    pdf_bytes = _build_pdf(
        year=year, month=month, month_label=month_label,
        total_month=total_month, total_prev=total_prev,
        count_month=count_month, avg_tx=avg_tx, delta_pct=delta_pct,
        categories=categories, top10=top10,
        budget_rows=budget_rows, anomalies=anomalies,
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
