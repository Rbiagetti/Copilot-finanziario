import os
import re
import json
import logging
from datetime import date, timedelta
from collections import defaultdict

from sqlalchemy import text
from openai import OpenAI

from backend.core.database import engine

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

# ─── BLOCK A — CONSTANTS & PRE-FILTER ────────────────────────────────────────

MAX_QUESTION_CHARS          = 500
MAX_HISTORY_MESSAGES        = 4
MAX_HISTORY_CHARS_PER_MSG   = 300
MAX_DATA_SUMMARY_ROWS       = 12
MAX_FOLLOWUP_QUESTIONS      = 2

# ─── BLOCK A — FUNCTION OUTPUT BOUNDS ────────────────────────────────────────
MAX_TABLE_ROWS              = 30
MAX_CHART_POINTS            = 24
MAX_PERIOD_DAYS             = 365
MAX_TOP_N                   = 50
MAX_CATEGORY_TREND_MONTHS   = 24

# Known categories — used to validate router-supplied category params.
# Treated as a soft allowlist: unrecognised values are set to None.
CATEGORIES: frozenset = frozenset({
    "abbigliamento", "abbonamenti", "altro", "casa", "cibo",
    "formazione", "intrattenimento", "lavoro", "salute", "svago", "trasporti",
})

_DEBUG_LOG_ROUTING = os.getenv("AI_DEBUG_ROUTING", "0") == "1"

# Precompiled OOS patterns — 7 domains
_OOS_PATTERNS: list = [
    # cucina / ricette
    re.compile(
        r"\b(ricett[ae]|ingredienti\s+per|come\s+si\s+cucina|cuoc[ei]|carbonara|risotto\s+(?:al|alla)|pizza\s+(?:fatta|napoletana)|pane\s+(?:da|di|fatto))\b",
        re.IGNORECASE,
    ),
    # sport
    re.compile(
        r"\b(partita\s+di\s+(?:calcio|basket|tennis)|chi\s+ha\s+vinto\s+la\s+partita|campionato\s+di\s+(?:calcio|basket)|champions\s+league|formula\s+1\s+(?:gara|pilota|classifica)|motogp\s+(?:gara|classifica))\b",
        re.IGNORECASE,
    ),
    # meteo
    re.compile(
        r"\b(previsioni\s+(?:del\s+)?meteo|che\s+tempo\s+fa|come\s+sar[aà]\s+il\s+tempo|temperatura\s+(?:domani|oggi\s+fuori)|piover[aà]\s+(?:domani|oggi)|allerta\s+meteo)\b",
        re.IGNORECASE,
    ),
    # codice / programmazione
    re.compile(
        r"\b(scrivi(?:mi)?\s+(?:un[ao]?\s+)?(?:funzione|programma|script|algoritmo|codice)|come\s+si\s+programma|in\s+(?:python|javascript|java|c\+\+)\s+(?:come|scrivi|crea)|fare\s+(?:un\s+)?debug)\b",
        re.IGNORECASE,
    ),
    # geopolitica
    re.compile(
        r"\b(guerra\s+(?:in|tra|di)\s+\w+|chi\s+ha\s+vinto\s+(?:la\s+)?(?:guerra|le\s+elezioni)|elezioni?\s+(?:politiche|presidenziali)|chi\s+[eèé]\s+il\s+presidente|presidente\s+(?:degli\s+stati|usa\b|della\s+russia))\b",
        re.IGNORECASE,
    ),
    # meta-AI
    re.compile(
        r"\b(sei\s+un[a']?\s+(?:intelligenza\s+artificiale|robot|bot|ai\b|llm)|come\s+sei\s+stato\s+(?:creato|addestrato|programmato)|chi\s+ti\s+ha\s+(?:creato|fatto|programmato)|che\s+modello\s+sei)\b",
        re.IGNORECASE,
    ),
    # salute
    re.compile(
        r"\b(quante\s+calorie\s+(?:ha|in)\s+\w+|dieta\s+per\s+(?:dimagrire|perdere\s+peso)|sintomi\s+(?:di|del)\s+\w+|quali?\s+farmaci?\s+(?:per|prendere)|come\s+si\s+cura\s+|mal\s+di\s+(?:testa|schiena|stomaco|denti)|ho\s+(?:la\s+)?febbre)\b",
        re.IGNORECASE,
    ),
]


def _is_obviously_out_of_scope(question: str) -> bool:
    """Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM."""
    for pattern in _OOS_PATTERNS:
        if pattern.search(question):
            if _DEBUG_LOG_ROUTING:
                logger.debug("PRE-FILTER OOS match pattern=%r question=%r", pattern.pattern, question[:80])
            return True
    return False


def _input_too_long(question: str) -> bool:
    """Ritorna True se la domanda supera i limiti di lunghezza."""
    return len(question) > MAX_QUESTION_CHARS or question.count(" ") > 80


_OUT_OF_SCOPE_PREFILTER = {
    "answer": (
        "Sono specializzato in analisi finanziarie personali e non posso rispondere "
        "a domande su cucina, sport, meteo, programmazione o altri argomenti.\n\n"
        "Posso aiutarti con:\n"
        "• **Spese per categoria** — questo mese o periodo custom\n"
        "• **Top transazioni** più costose (con filtro per categoria)\n"
        "• **Trend giornaliero** delle spese\n"
        "• **Confronto mese** corrente vs precedente\n"
        "• **Statistiche** riassuntive (totale, media, conteggio)"
    ),
    "followup_questions": [
        "Quali categorie hanno pesato di più questo mese?",
        "Mostrami le 10 spese più alte degli ultimi 30 giorni",
    ],
}

_INPUT_TOO_LONG = {
    "answer": "La domanda è troppo lunga. Prova a riformularla in modo più conciso (massimo 500 caratteri).",
    "followup_questions": [],
}


# ─── BLOCK C — TOKEN COUNTER & LLM WRAPPER ───────────────────────────────────

_token_counter: dict = {"calls": 0, "by_phase": defaultdict(int)}

# None = not yet tested, True = supported, False = not supported
_llm_state: dict = {"response_format_supported": None}


def _llm_call(
    phase: str,
    messages: list,
    temperature: float,
    max_tokens: int,
    seed: int = None,
    json_mode: bool = False,
) -> str:
    """Wrapper LLM centralizzato con contatore chiamate e json_mode con fallback."""
    _token_counter["calls"] += 1
    _token_counter["by_phase"][phase] += 1

    kwargs: dict = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if seed is not None:
        kwargs["seed"] = seed

    if json_mode:
        supported = _llm_state["response_format_supported"]
        if supported is None or supported is True:
            try:
                kwargs["response_format"] = {"type": "json_object"}
                response = client.chat.completions.create(**kwargs)
                _llm_state["response_format_supported"] = True
                return response.choices[0].message.content.strip()
            except Exception:
                # Log once that json_mode is not supported on this endpoint
                if _llm_state["response_format_supported"] is None:
                    logger.warning("response_format json_object not supported — falling back to plain text")
                _llm_state["response_format_supported"] = False
                kwargs.pop("response_format", None)
                response = client.chat.completions.create(**kwargs)
                return response.choices[0].message.content.strip()
        # json_mode unsupported: proceed without it
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content.strip()

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content.strip()


def get_llm_stats() -> dict:
    """Ritorna le statistiche sulle chiamate LLM dall'avvio del processo."""
    return {
        "total_calls": _token_counter["calls"],
        "by_phase": dict(_token_counter["by_phase"]),
        "json_mode_supported": _llm_state["response_format_supported"],
    }


# ─── BLOCK C — HISTORY SANITIZER ─────────────────────────────────────────────

def _sanitize_history(history) -> list:
    """Taglia la history a MAX_HISTORY_MESSAGES e trunca i messaggi lunghi."""
    if not history:
        return []
    trimmed = list(history)[-MAX_HISTORY_MESSAGES:]
    result = []
    for msg in trimmed:
        role = msg.get("role", "user")
        content = str(msg.get("content", ""))
        if len(content) > MAX_HISTORY_CHARS_PER_MSG:
            content = content[:MAX_HISTORY_CHARS_PER_MSG] + "…"
        result.append({"role": role, "content": content})
    return result


# ─── DB HELPERS ───────────────────────────────────────────────────────────────

def _q(sql: str, params: dict = None):
    """Esegue una query e restituisce tutte le righe."""
    with engine.connect() as conn:
        return conn.execute(text(sql), params or {}).fetchall()


def _scalar(sql: str, params: dict = None):
    """Esegue una query e restituisce il primo valore della prima riga."""
    with engine.connect() as conn:
        row = conn.execute(text(sql), params or {}).fetchone()
        return row[0] if row else None


def _dates(days_ago: int = 0) -> str:
    """Restituisce la data ISO di N giorni fa."""
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _month_start(months_back: int = 0) -> str:
    """Primo giorno del mese corrente (o N mesi fa)."""
    d = date.today().replace(day=1)
    for _ in range(months_back):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.isoformat()


def build_context() -> str:
    """Costruisce il contesto del DB per il prompt AI."""
    d30 = _dates(30)
    d60 = _dates(60)

    schema = "transactions(id, amount REAL, category TEXT, description TEXT, date TEXT)"
    total_all = _scalar("SELECT COUNT(*) FROM transactions") or 0
    date_range = _q("SELECT MIN(date), MAX(date) FROM transactions")
    dr = date_range[0] if date_range else (None, None)
    grand_total = round(_scalar("SELECT SUM(amount) FROM transactions") or 0, 2)

    row = _q("SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d", {"d": d30})
    last_30_total = round(row[0][0] or 0, 2) if row else 0
    last_30_count = row[0][1] or 0 if row else 0

    prev_30 = round(_scalar(
        "SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30",
        {"d60": d60, "d30": d30}
    ) or 0, 2)

    cat_30 = _q(
        "SELECT category, COUNT(*), SUM(amount), AVG(amount) FROM transactions "
        "WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC",
        {"d": d30}
    )

    total_30_pct = round((last_30_total - prev_30) / prev_30 * 100, 1) if prev_30 > 0 else 0
    trend = f"+{total_30_pct}%" if total_30_pct >= 0 else f"{total_30_pct}%"

    cats_30_str = "\n".join(
        f"  - {c[0]}: {c[1]} tx, €{round(c[2],2)} "
        f"({round(c[2]/last_30_total*100) if last_30_total>0 else 0}% del mese), media €{round(c[3],2)}"
        for c in cat_30
    ) if cat_30 else "  (nessuna transazione)"

    return (
        f"SCHEMA: {schema}\n"
        f"STORICO TOTALE: {total_all} transazioni, €{grand_total}, range {dr[0]} → {dr[1]}\n"
        f"ULTIMI 30 GIORNI: €{last_30_total} ({last_30_count} transazioni, {trend} vs mese precedente €{prev_30})\n"
        f"CATEGORIE ULTIMI 30 GIORNI (usa QUESTI dati per il briefing, NON lo storico):\n{cats_30_str}"
    )


# ─── FUNZIONI PRECONFEZIONATE ─────────────────────────────────────────────────

FUNCTION_CATALOG = {
    "spending_by_category": {
        "desc": "Spese per categoria in un periodo. Grafico a barre.",
        "params": "period_days: int=30",
    },
    "daily_trend": {
        "desc": "Trend giornaliero delle spese. Grafico a linee.",
        "params": "days: int=30",
    },
    "top_transactions": {
        "desc": "Tabella delle N transazioni piu' costose con dettagli.",
        "params": "n: int=10, category: str=null, period_days: int=30",
    },
    "month_vs_month": {
        "desc": "Confronto spese mese corrente vs precedente per categoria.",
        "params": "(nessuno)",
    },
    "spending_by_weekday": {
        "desc": "Media spese per giorno della settimana (Lun-Dom).",
        "params": "period_days: int=90",
    },
    "category_trend": {
        "desc": "Andamento mensile di una categoria negli ultimi N mesi.",
        "params": "category: str, months: int=6",
    },
    "summary_stats": {
        "desc": "Statistiche riassuntive: totale, media transazione, n. transazioni, categoria top.",
        "params": "period_days: int=30",
    },
    "year_end_forecast": {
        "desc": "Proiezione spese fino a fine anno basata sulla media giornaliera recente.",
        "params": "(nessuno)",
    },
}

_CATALOG_WIKI = "\n".join(
    f"  - {name}({meta['params']}): {meta['desc']}"
    for name, meta in FUNCTION_CATALOG.items()
)


def _fn_spending_by_category(db_path: str, params: dict) -> dict:
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 30))))
    chart_type = params.get("chart_type", "bar")
    if chart_type not in ("bar", "line", "pie"):
        chart_type = "bar"
    cutoff = _dates(period_days)
    rows = _q(
        "SELECT category, SUM(amount) FROM transactions "
        "WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC "
        "LIMIT :lim",
        {"d": cutoff, "lim": MAX_CHART_POINTS}
    )
    data = [{"name": r[0], "value": round(r[1], 2)} for r in rows if r[1] and r[1] > 0]
    return {
        "chart_data": {"type": chart_type, "data": data, "title": f"Spese per categoria (ultimi {period_days}gg)"},
        "table_data": None,
    }


def _fn_daily_trend(db_path: str, params: dict) -> dict:
    days = max(1, min(MAX_PERIOD_DAYS, int(params.get("days", 30))))
    cutoff = _dates(days)
    # Take the most recent MAX_CHART_POINTS days, then re-sort ascending for the chart
    rows = _q(
        "SELECT date, SUM(amount) FROM transactions "
        "WHERE date >= :d GROUP BY date ORDER BY date DESC "
        "LIMIT :lim",
        {"d": cutoff, "lim": MAX_CHART_POINTS}
    )
    rows = sorted(rows, key=lambda r: r[0])
    data = [{"name": r[0][5:], "value": round(r[1], 2)} for r in rows]
    return {
        "chart_data": {"type": "line", "data": data, "title": f"Trend giornaliero (ultimi {days}gg)"},
        "table_data": None,
    }


def _fn_top_transactions(db_path: str, params: dict) -> dict:
    n = max(1, min(MAX_TOP_N, int(params.get("n", 10))))
    category = params.get("category")
    if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
        category = None
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 30))))
    cutoff = _dates(period_days)
    if category:
        rows = _q(
            "SELECT date, category, description, amount FROM transactions "
            "WHERE date >= :d AND category = :cat ORDER BY amount DESC LIMIT :n",
            {"d": cutoff, "cat": category, "n": n}
        )
    else:
        rows = _q(
            "SELECT date, category, description, amount FROM transactions "
            "WHERE date >= :d ORDER BY amount DESC LIMIT :n",
            {"d": cutoff, "n": n}
        )
    return {
        "chart_data": None,
        "table_data": {
            "headers": ["Data", "Categoria", "Descrizione", "Importo"],
            "rows": [[r[0], r[1], r[2] or "-", f"€{round(r[3],2)}"] for r in rows],
        },
    }


def _fn_month_vs_month(db_path: str, params: dict) -> dict:
    ms = _month_start(0)   # inizio mese corrente
    pms = _month_start(1)  # inizio mese precedente

    rows = _q(
        "SELECT category, "
        "SUM(CASE WHEN date >= :ms THEN amount ELSE 0 END) as curr, "
        "SUM(CASE WHEN date >= :pms AND date < :ms THEN amount ELSE 0 END) as prev "
        "FROM transactions WHERE date >= :pms "
        "GROUP BY category ORDER BY curr DESC "
        "LIMIT :lim",
        {"ms": ms, "pms": pms, "lim": MAX_TABLE_ROWS}
    )
    table = {
        "headers": ["Categoria", "Mese corrente", "Mese prec.", "Variazione"],
        "rows": [
            [r[0], f"€{round(r[1],2)}", f"€{round(r[2],2)}",
             f"+{round((r[1]-r[2])/r[2]*100)}%" if r[2] > 0 else "N/A"]
            for r in rows if (r[1] or 0) > 0 or (r[2] or 0) > 0
        ][:MAX_TABLE_ROWS],
    }
    data = [{"name": r[0], "value": round(r[1], 2)} for r in rows if (r[1] or 0) > 0]
    return {
        "chart_data": {"type": "bar", "data": data, "title": "Spese mese corrente per categoria"},
        "table_data": table,
    }


def _fn_spending_by_weekday(db_path: str, params: dict) -> dict:
    from datetime import datetime as _dt
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)
    rows = _q(
        "SELECT date, SUM(amount) FROM transactions WHERE date >= :d GROUP BY date",
        {"d": cutoff}
    )
    dow_vals: dict = defaultdict(list)
    for date_str, total in rows:
        try:
            weekday = _dt.strptime(date_str, "%Y-%m-%d").weekday()  # 0=Lun, 6=Dom
            dow_sun = (weekday + 1) % 7  # 0=Dom, 1=Lun, ..., 6=Sab
        except ValueError:
            continue
        dow_vals[dow_sun].append(total or 0)

    day_names = ["Dom", "Lun", "Mar", "Mer", "Gio", "Ven", "Sab"]
    data = [
        {"name": day_names[dow], "value": round(sum(vals) / len(vals), 2)}
        for dow, vals in sorted(dow_vals.items())
    ]
    return {
        "chart_data": {"type": "bar", "data": data, "title": "Media spese per giorno della settimana"},
        "table_data": None,
    }


def _fn_category_trend(db_path: str, params: dict) -> dict:
    category = params.get("category", "cibo")
    if not isinstance(category, str) or category not in CATEGORIES:
        category = "cibo"
    months = max(1, min(MAX_CATEGORY_TREND_MONTHS, int(params.get("months", 6))))
    cutoff = _dates(months * 30)
    rows = _q(
        "SELECT date, amount FROM transactions WHERE category = :cat AND date >= :d ORDER BY date",
        {"cat": category, "d": cutoff}
    )
    monthly: dict = defaultdict(float)
    for date_str, amount in rows:
        monthly[date_str[:7]] += amount or 0
    # Take the most recent MAX_CHART_POINTS months
    sorted_months = sorted(monthly.items())[-MAX_CHART_POINTS:]
    data = [{"name": k, "value": round(v, 2)} for k, v in sorted_months]
    return {
        "chart_data": {"type": "line", "data": data, "title": f"Andamento mensile: {category}"},
        "table_data": None,
    }


def _fn_year_end_forecast(db_path: str, params: dict) -> dict:
    today = date.today()
    d30 = _dates(30)
    year_start = today.replace(month=1, day=1).isoformat()

    total_30 = round(_scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d", {"d": d30}) or 0, 2)
    spent_ytd = round(_scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d", {"d": year_start}) or 0, 2)

    days_remaining = (date(today.year, 12, 31) - today).days
    daily_avg = round(total_30 / 30, 2) if total_30 > 0 else 0
    projected_remaining = round(daily_avg * days_remaining, 2)
    projected_total = round(spent_ytd + projected_remaining, 2)

    return {
        "chart_data": {
            "type": "bar",
            "data": [
                {"name": "Già speso (YTD)", "value": spent_ytd},
                {"name": f"Previsto ({days_remaining}gg)", "value": projected_remaining},
            ],
            "title": f"Proiezione spese fine anno {today.year}",
        },
        "table_data": {
            "headers": ["Metrica", "Valore"],
            "rows": [
                ["Speso da inizio anno", f"€{spent_ytd}"],
                ["Media giornaliera (ultimi 30gg)", f"€{daily_avg}"],
                ["Giorni rimasti all'anno", str(days_remaining)],
                ["Previsto per il resto dell'anno", f"€{projected_remaining}"],
                ["Totale proiettato anno", f"€{projected_total}"],
            ],
        },
    }


def _fn_summary_stats(db_path: str, params: dict) -> dict:
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 30))))
    cutoff = _dates(period_days)
    row = _q(
        "SELECT SUM(amount), COUNT(*), AVG(amount) FROM transactions WHERE date >= :d",
        {"d": cutoff}
    )
    total, count, avg = (round(row[0][0] or 0, 2), row[0][1] or 0, round(row[0][2] or 0, 2)) if row else (0, 0, 0)
    top_cat = _q(
        "SELECT category FROM transactions WHERE date >= :d "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        {"d": cutoff}
    )
    return {
        "chart_data": None,
        "table_data": {
            "headers": ["Metrica", "Valore"],
            "rows": [
                ["Totale spese", f"€{total}"],
                ["Transazioni", str(count)],
                ["Media per transazione", f"€{avg}"],
                ["Categoria top", top_cat[0][0] if top_cat else "-"],
                ["Periodo analizzato", f"ultimi {period_days}gg"],
            ],
        },
    }


_PREBUILT_FUNCTIONS = {
    "spending_by_category": _fn_spending_by_category,
    "daily_trend": _fn_daily_trend,
    "top_transactions": _fn_top_transactions,
    "month_vs_month": _fn_month_vs_month,
    "spending_by_weekday": _fn_spending_by_weekday,
    "category_trend": _fn_category_trend,
    "summary_stats": _fn_summary_stats,
    "year_end_forecast": _fn_year_end_forecast,
}


def _validate_function_output(out: dict) -> dict:
    """Normalizza e clippa l'output di ogni funzione prebuilt prima di ritornarlo."""
    if not isinstance(out, dict):
        return {"chart_data": None, "table_data": None}

    # ── chart_data ───────────────────────────────────────────────────────────
    cd = out.get("chart_data")
    if cd is not None:
        if not isinstance(cd, dict):
            cd = None
        else:
            if cd.get("type") not in ("bar", "line", "pie"):
                cd["type"] = "bar"
            cd["title"] = str(cd.get("title", ""))[:80]
            data = cd.get("data")
            if not isinstance(data, list):
                cd = None
            else:
                cd["data"] = data[:MAX_CHART_POINTS]

    # ── table_data ───────────────────────────────────────────────────────────
    td = out.get("table_data")
    if td is not None:
        if not isinstance(td, dict):
            td = None
        else:
            rows = td.get("rows")
            if not isinstance(rows, list):
                td = None
            else:
                td["rows"] = [
                    [str(cell) for cell in row]
                    for row in rows[:MAX_TABLE_ROWS]
                ]

    return {"chart_data": cd, "table_data": td}


def execute_prebuilt_function(name: str, params: dict) -> dict:
    fn = _PREBUILT_FUNCTIONS.get(name)
    if not fn:
        return {"chart_data": None, "table_data": None}
    try:
        raw = fn(None, params or {})
        return _validate_function_output(raw)
    except Exception:
        return {"chart_data": None, "table_data": None}


# ─── PROMPTS ──────────────────────────────────────────────────────────────────

FUNCTION_SELECTOR_PROMPT = """Sei un router finanziario. Classifica la domanda in uno dei tre casi.

FUNZIONI DISPONIBILI (usa solo i parametri indicati, rispetta i range):
- spending_by_category(period_days=30, range 1..365): "dove vanno i soldi", "analisi completa", "distribuzione spese", "per categoria"
- daily_trend(days=30, range 1..365): "trend giornaliero", "grafico spese nel tempo", "giorno per giorno"
- top_transactions(n=10 range 1..50, category=null, period_days=30 range 1..365): "spese piu' alte", "transazioni piu' costose", "top N"
- month_vs_month(): "confronto mesi", "questo mese vs mese scorso", "variazione mensile"
- spending_by_weekday(period_days=90, range 1..365): "weekend vs feriali", "giorno piu' costoso", "media per giorno settimana"
- category_trend(category, months=6 range 1..24): "andamento [categoria] nel tempo", "storico [categoria] mesi"
- summary_stats(period_days=30, range 1..365): "statistiche generali", "totale e media", "quante transazioni"
- year_end_forecast(): "stima fine anno", "previsione annuale", "quanto spendero' entro dicembre"

CASO 1 — c'e' una funzione adatta:
{"use_function": {"name": "nome", "params": {...}}, "in_perimeter": true}

CASO 2 — domanda finanziaria/budget ma nessuna funzione la copre (consigli, simulazioni semplici, domande sul comportamento di spesa):
{"use_function": null, "in_perimeter": true}

CASO 3 — domanda NON finanziaria (cucina, sport, coding, ecc.):
{"use_function": null, "in_perimeter": false}

Rispondi SOLO JSON (no testo extra):"""

INTERPRET_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DOMANDA: {question}

DATI:
{data_summary}

Scrivi 2-3 frasi da consulente. REGOLE:
- Usa numeri ESATTI dai dati (importi, nomi, date)
- Identifica il pattern principale o l'anomalia piu' interessante
- NON dire "la tabella mostra", "ecco i dati" — analizza direttamente
- Usa **grassetto** per cifre o categorie chiave
- Chiudi con 1 raccomandazione concreta

Poi 1-2 domande di approfondimento nel campo followup_questions — domande che l'UTENTE farebbe all'AI.
Esempi corretti: "Mostrami il trend dell'abbigliamento negli ultimi 6 mesi", "Quali sono le 5 spese piu' alte di trasporti?"
NON includere suggerimenti di domande dentro il campo answer. Il campo answer contiene SOLO l'analisi.

SOLO JSON: {{"answer": "...", "followup_questions": ["...", "..."]}}"""

TEXT_ANSWER_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DATI UTENTE (ultimi 30gg):
{compact_context}

Rispondi alla domanda in 2-4 frasi. REGOLE:
- Usa i numeri dal contesto quando utile
- Sii diretto e pratico, dai consigli concreti
- Usa **grassetto** per cifre o concetti chiave
- Se non hai dati sufficienti per rispondere con certezza, dillo chiaramente

Poi 1-2 domande di approfondimento nel campo followup_questions — domande che l'UTENTE farebbe all'AI.
Esempi corretti: "Mostrami il trend del cibo negli ultimi 3 mesi", "Qual e' la mia spesa media settimanale?"
NON includere suggerimenti di domande dentro il campo answer. Il campo answer contiene SOLO la risposta.

SOLO JSON: {{"answer": "...", "followup_questions": ["...", "..."]}}"""

_OUT_OF_SCOPE = {
    "answer": (
        "Questa analisi non è ancora disponibile. Posso aiutarti con:\n\n"
        "• **Spese per categoria** — questo mese o periodo custom\n"
        "• **Top transazioni** più costose (con filtro per categoria)\n"
        "• **Trend giornaliero** delle spese\n"
        "• **Confronto mese** corrente vs precedente\n"
        "• **Media per giorno** della settimana\n"
        "• **Andamento mensile** di una categoria specifica\n"
        "• **Statistiche** riassuntive (totale, media, conteggio)"
    ),
    "followup_questions": [
        "Quali categorie hanno pesato di più questo mese?",
        "Mostrami le 10 spese più alte degli ultimi 30 giorni",
    ],
}


# ─── BLOCK B — ROUTER VALIDATION ─────────────────────────────────────────────

def _validate_router_output(parsed: dict) -> dict:
    """Sanitizza e valida l'output del router: nomi funzione, parametri, flag in_perimeter."""
    in_perimeter = bool(parsed.get("in_perimeter", True))

    use_function = parsed.get("use_function")
    if use_function is not None:
        if not isinstance(use_function, dict):
            use_function = None
        else:
            name = use_function.get("name", "")
            if name not in FUNCTION_CATALOG:
                if _DEBUG_LOG_ROUTING:
                    logger.debug("ROUTER invalid function name=%r — discarded", name)
                use_function = None
            else:
                params = dict(use_function.get("params") or {})
                # Clip integer params to safe ranges
                for key, lo, hi, default in [
                    ("period_days", 1, 365, 30),
                    ("days", 1, 365, 30),
                    ("n", 1, 50, 10),
                    ("months", 1, 24, 6),
                ]:
                    if key in params:
                        try:
                            params[key] = max(lo, min(hi, int(params[key])))
                        except (ValueError, TypeError):
                            params[key] = default
                # chart_type enum
                if "chart_type" in params:
                    if params["chart_type"] not in ("bar", "line"):
                        params["chart_type"] = "bar"
                # category must be a known CATEGORIES value or None
                if "category" in params and params["category"] is not None:
                    cat = params["category"]
                    if not isinstance(cat, str) or cat not in CATEGORIES:
                        params["category"] = None
                use_function = {"name": name, "params": params}

    return {"use_function": use_function, "in_perimeter": in_perimeter}


# ─── CORE AI FUNCTIONS ────────────────────────────────────────────────────────

def _format_data_for_interpretation(chart_data, table_data) -> str:
    parts = []
    if chart_data:
        parts.append(f"Grafico '{chart_data.get('title', '')}' ({chart_data.get('type', 'bar')}):")
        for item in chart_data.get("data", [])[:MAX_DATA_SUMMARY_ROWS]:
            parts.append(f"  {item.get('name')}: €{item.get('value')}")
    if table_data:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        parts.append(f"Tabella ({len(rows)} righe) — colonne: {', '.join(headers)}:")
        for row in rows[:MAX_DATA_SUMMARY_ROWS]:
            parts.append("  " + " | ".join(str(c) for c in row))
    return "\n".join(parts) if parts else "Nessun dato trovato."


def build_compact_context() -> str:
    """Contesto minimo per risposte testuali: solo totali e top categorie."""
    d30 = _dates(30)
    d60 = _dates(60)
    row = _q("SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d", {"d": d30})
    total = round(row[0][0] or 0, 2) if row else 0
    count = row[0][1] or 0 if row else 0
    prev = round(_scalar(
        "SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30",
        {"d60": d60, "d30": d30}
    ) or 0, 2)
    cats = _q(
        "SELECT category, SUM(amount) FROM transactions WHERE date >= :d "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5",
        {"d": d30}
    )
    trend = f"+{round((total-prev)/prev*100,1)}%" if prev > 0 else "N/D"
    cats_str = ", ".join(f"{c[0]} €{round(c[1],2)}" for c in cats)
    return f"Totale 30gg: €{total} ({count} tx, {trend} vs mese prec.) | Top categorie: {cats_str}"


def _parse_ai_response(raw: str) -> dict:
    # Fast-path: empty or no JSON object at all
    if not raw or "{" not in raw:
        return {"answer": raw or "", "followup_questions": []}

    cleaned = raw
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    answer_match = re.search(r'"answer"\s*:\s*"((?:[^"\\]|\\.)*)"', cleaned)
    if answer_match:
        answer = answer_match.group(1).replace('\\"', '"').replace('\\n', '\n')
        followups = []
        fq_match = re.search(r'"followup_questions"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
        if fq_match:
            followups = re.findall(r'"((?:[^"\\]|\\.)*)"', fq_match.group(1))
        return {"answer": answer, "followup_questions": followups}

    return {"answer": raw, "followup_questions": []}


def _answer_in_perimeter(question: str, compact_context: str) -> dict:
    prompt = TEXT_ANSWER_PROMPT.format(compact_context=compact_context)
    raw = _llm_call(
        "answer",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.1,
        max_tokens=400,
        seed=42,
        json_mode=True,
    )
    return _parse_ai_response(raw)


def _select_function(question: str, history) -> dict:
    messages = [{"role": "system", "content": FUNCTION_SELECTOR_PROMPT}]
    clean_history = _sanitize_history(history)
    # Pass only last 2 user turns for context
    for h in clean_history[-2:]:
        if h.get("role") == "user":
            messages.append({"role": "user", "content": h.get("content", "")})
    messages.append({"role": "user", "content": question})

    raw = _llm_call(
        "router",
        messages=messages,
        temperature=0.0,
        max_tokens=150,
        seed=42,
        json_mode=True,
    )

    parsed = _parse_ai_response(raw)
    validated = _validate_router_output(parsed)

    if _DEBUG_LOG_ROUTING:
        logger.debug("ROUTER raw=%r  validated=%r", raw[:200], validated)

    return validated


def _interpret_results(question: str, data_summary: str) -> dict:
    prompt = INTERPRET_PROMPT.format(question=question, data_summary=data_summary)
    raw = _llm_call(
        "interpret",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analizza."},
        ],
        temperature=0.1,
        max_tokens=400,
        seed=42,
        json_mode=True,
    )
    return _parse_ai_response(raw)


# ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────────

def chat_with_ai(question: str, history=None) -> dict:
    # ── Block A: Pre-filter (zero LLM calls) ──────────────────────────────────
    if _input_too_long(question):
        return {
            "answer": _INPUT_TOO_LONG["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _INPUT_TOO_LONG["followup_questions"],
        }

    if _is_obviously_out_of_scope(question):
        return {
            "answer": _OUT_OF_SCOPE_PREFILTER["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE_PREFILTER["followup_questions"],
        }

    # ── Block B: Router with determinism & validation ─────────────────────────
    selector = _select_function(question, history)
    use_function = selector.get("use_function")
    in_perimeter = selector.get("in_perimeter", True)

    if not in_perimeter:
        return {
            "answer": _OUT_OF_SCOPE["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE["followup_questions"],
        }

    if use_function and isinstance(use_function, dict):
        fn_result = execute_prebuilt_function(
            use_function.get("name", ""),
            use_function.get("params") or {},
        )
        chart_data = fn_result.get("chart_data")
        table_data = fn_result.get("table_data")
        data_summary = _format_data_for_interpretation(chart_data, table_data)
        interp = _interpret_results(question, data_summary)
        return {
            "answer": interp.get("answer", "Analisi completata.").strip(),
            "chart_data": chart_data,
            "data_table": table_data,
            "followup_questions": interp.get("followup_questions", [])[:MAX_FOLLOWUP_QUESTIONS],
        }

    compact_ctx = build_compact_context()
    interp = _answer_in_perimeter(question, compact_ctx)
    return {
        "answer": interp.get("answer", "").strip(),
        "chart_data": None,
        "data_table": None,
        "followup_questions": interp.get("followup_questions", [])[:MAX_FOLLOWUP_QUESTIONS],
    }


# ─── BRIEFING & ANOMALIES (unchanged logic, updated LLM calls) ───────────────

BRIEFING_PROMPT = """Sei un analista finanziario AI. Hai accesso ai dati REALI dell'utente:

{context}

REGOLA ASSOLUTA: usa SOLO i dati "ULTIMI 30 GIORNI" e "CATEGORIE ULTIMI 30 GIORNI". NON usare mai lo storico totale per il briefing.

Produci 3 insight sul mese corrente (ultimi 30 giorni). Rispondi SOLO con JSON (no markdown, no backtick):
{{"insights": [{{"title": "...", "body": "...", "type": "positive|warning|info"}}], "action": "..."}}

Regole OBBLIGATORIE:
- Ogni body usa numeri reali dai DATI MENSILI (non dal totale storico)
- type: "warning" se categoria > 30% del mensile o trend positivo, "positive" se in calo, "info" neutro
- "action" cita categoria specifica con €importo MENSILE reale e suggerimento concreto
- Se trend vs mese prec. e' disponibile, citalo nell'insight principale
- Rispondi in italiano"""

_briefing_cache: dict = {"data": None, "ts": 0.0}


def generate_briefing() -> dict:
    import time
    now = time.time()
    if _briefing_cache["data"] and (now - _briefing_cache["ts"]) < 3600:
        return _briefing_cache["data"]

    context = build_context()
    try:
        raw = _llm_call(
            "briefing",
            messages=[
                {"role": "system", "content": BRIEFING_PROMPT.format(context=context)},
                {"role": "user", "content": "Dammi il briefing finanziario di oggi."},
            ],
            temperature=0.2,
            max_tokens=600,
            json_mode=True,
        )
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r'\{[\s\S]*\}', raw)
            result = json.loads(m.group()) if m else None

        if result and "insights" in result:
            _briefing_cache["data"] = result
            _briefing_cache["ts"] = now
            return result
    except Exception:
        pass

    return {
        "insights": [
            {"title": "Dati caricati", "body": "Il tuo storico e' disponibile per l'analisi.", "type": "info"},
        ],
        "action": "Fai una domanda nella chat per analizzare le tue spese.",
    }


def get_anomalies() -> list:
    import statistics
    d60 = _dates(60)
    rows = _q(
        "SELECT id, amount, category, description, date FROM transactions "
        "WHERE date >= :d ORDER BY date DESC",
        {"d": d60}
    )
    if not rows:
        return []

    by_cat: dict = defaultdict(list)
    for row in rows:
        by_cat[row[2]].append(row)

    anomalies = []
    for cat, cat_rows in by_cat.items():
        if len(cat_rows) < 3:
            continue
        amounts = [r[1] for r in cat_rows]
        mean = statistics.mean(amounts)
        stdev = statistics.stdev(amounts) if len(amounts) > 1 else 0
        if stdev == 0:
            continue
        for row in cat_rows:
            z = (row[1] - mean) / stdev
            if z > 1.5:
                anomalies.append({
                    "id": row[0],
                    "amount": round(row[1], 2),
                    "category": row[2],
                    "description": row[3] or "",
                    "date": row[4],
                    "z_score": round(z, 2),
                    "avg_category": round(mean, 2),
                    "pct_above_avg": round((row[1] - mean) / mean * 100) if mean > 0 else 0,
                })

    anomalies.sort(key=lambda x: x["z_score"], reverse=True)
    return anomalies[:5]
