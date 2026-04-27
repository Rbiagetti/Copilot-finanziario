import os
import re
import json
import logging
import time as _time
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
MAX_MULTI_SUMMARY_CHARS     = 2500

# Known categories — used to validate router-supplied category params.
# Treated as a soft allowlist: unrecognised values are set to None.
CATEGORIES: frozenset = frozenset({
    "abbigliamento", "abbonamenti", "altro", "casa", "cibo",
    "formazione", "intrattenimento", "lavoro", "salute", "svago", "trasporti",
})

MACRO_INTENTS: dict = {
    "full_monthly_review": {
        "triggers": ["analisi completa", "riassunto del mese", "panoramica", "dimmi tutto", "come sto andando"],
        "functions": [
            ("month_vs_month",           {}),
            ("spending_by_category",     {"period_days": 30}),
            ("anomalies",                {}),
            ("budget_status",            {}),
        ],
    },
    "savings_audit": {
        "triggers": ["dove posso risparmiare", "come tagliare", "ottimizzare spese", "ridurre spesa"],
        "functions": [
            ("subscriptions_audit",      {}),
            ("category_volatility",      {"period_days": 180}),
            ("concentration_risk",       {"period_days": 30}),
        ],
    },
    "trend_overview": {
        "triggers": ["come sto cambiando", "trend generale", "evoluzione spese", "andamento"],
        "functions": [
            ("daily_trend",              {"days": 60}),
            ("momentum",                 {}),
            ("month_vs_month",           {}),
        ],
    },
}

_DEBUG_LOG_ROUTING  = os.getenv("AI_DEBUG_ROUTING",   "0") == "1"
AI_DISABLE_LLM      = os.getenv("AI_DISABLE_LLM",    "0") == "1"   # salta LLM → OUT_OF_SCOPE in <10ms
AI_FORCE_TEMP_ZERO  = os.getenv("AI_FORCE_TEMP_ZERO", "0") == "1"  # forza temperature=0 su interpret/answer

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
    # meta-AI (include "sei chatgpt/gpt/gemini/claude")
    re.compile(
        r"\b(sei\s+(?:un[a']?\s+(?:intelligenza\s+artificiale|robot|bot|ai\b|llm)|chatgpt|gpt[-\s]?\d*|gemini|bard|copilot|claude)|come\s+sei\s+stato\s+(?:creato|addestrato|programmato)|chi\s+ti\s+ha\s+(?:creato|fatto|programmato)|che\s+modello\s+sei)\b",
        re.IGNORECASE,
    ),
    # salute
    re.compile(
        r"\b(quante\s+calorie\s+(?:ha|in)\s+\w+|dieta\s+per\s+(?:dimagrire|perdere\s+peso)|sintomi\s+(?:di|del)\s+\w+|quali?\s+farmaci?\s+(?:per|prendere)|come\s+si\s+cura\s+|mal\s+di\s+(?:testa|schiena|stomaco|denti)|ho\s+(?:la\s+)?febbre)\b",
        re.IGNORECASE,
    ),
    # intrattenimento non finanziario (serie TV, film, musica, libri da leggere)
    re.compile(
        r"\b(consigliami\s+(?:una\s+serie|un\s+film|una\s+canzone|un\s+libro\s+da\s+leggere|qualcosa\s+da\s+(?:vedere|guardare|ascoltare))|che\s+serie\s+(?:guardi|vedere)|migliori?\s+serie\s+(?:su|del|di\s+netflix|amazon)|cosa\s+(?:guardo|vedo|ascolto)\s+stasera)\b",
        re.IGNORECASE,
    ),
]


def _input_meaningless(question: str) -> bool:
    """True se l'input non contiene abbastanza caratteri alfabetici per essere una domanda."""
    alpha_count = sum(1 for c in question if c.isalpha())
    return alpha_count < 2


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

    # AI_FORCE_TEMP_ZERO: applica solo su interpret/answer/text (il router è già a 0)
    if AI_FORCE_TEMP_ZERO and phase not in ("router",):
        temperature = 0.0

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


def _reset_llm_stats() -> None:
    """Azzera i contatori LLM. Usato dal test harness prima di ogni caso."""
    _token_counter["calls"] = 0
    _token_counter["by_phase"].clear()


def _step(steps: list, phase: str, label: str, detail: str,
          t_start: float, status: str = "ok") -> None:
    """Aggiunge un passo di reasoning alla lista steps."""
    steps.append({
        "phase":       phase,
        "label":       label[:60],
        "detail":      str(detail)[:120],
        "duration_ms": int((_time.time() - t_start) * 1000),
        "status":      status,
    })


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
    "anomalies": {
        "desc": "Transazioni statisticamente anomale (z-score > 1.5) negli ultimi 60 giorni.",
        "params": "(nessuno)",
    },
    "budget_status": {
        "desc": "Stato budget attivi: speso vs budget mensile per categoria, con semaforo ok/warning/exceeded.",
        "params": "(nessuno)",
    },
    "recurring_vs_variable": {
        "desc": "Spese ricorrenti vs variabili per mese, ultimi N giorni.",
        "params": "period_days: int=90",
    },
    "subscriptions_audit": {
        "desc": "Lista abbonamenti attivi (is_recurring=1, >=2 addebiti): importo medio, annualizzato.",
        "params": "(nessuno)",
    },
    # ── Advanced analytics ──────────────────────────────────────────────────
    "category_volatility": {
        "desc": "Volatilità mensile per categoria: media, stdev, CV. Ordinate per imprevedibilità.",
        "params": "period_days: int=180",
    },
    "frequency_analysis": {
        "desc": "Frequenza transazioni per categoria: gap medio tra tx, media, mediana.",
        "params": "category: str=null, period_days: int=90",
    },
    "concentration_risk": {
        "desc": "Concentrazione spese: top 3 categorie, top 5 descrizioni, top 5 giorni più cari.",
        "params": "period_days: int=30",
    },
    "period_compare": {
        "desc": "Confronto due finestre temporali arbitrarie per categoria: delta€ e delta%.",
        "params": "period_a_days: int=30, period_b_offset_days: int=30",
    },
    "momentum": {
        "desc": "Regressione lineare settimanale: trend %/settimana, classificazione accelerazione/stabile/decelerazione.",
        "params": "category: str=null, period_days: int=60",
    },
    # ── Ricerca e drilldown ─────────────────────────────────────────────────
    "search_transactions": {
        "desc": "Ricerca LIKE case-insensitive su description+tags, con trend giornaliero del subset.",
        "params": "query: str, period_days: int=90, n: int=20",
    },
    "category_drill": {
        "desc": "Drilldown completo di una categoria: statistiche, top 5 descrizioni, top 5 giorni.",
        "params": "category: str, period_days: int=90",
    },
    "tag_analysis": {
        "desc": "Analisi tag: tag specificato → transazioni e trend; tag null → top 10 tag per spesa.",
        "params": "tag: str=null, period_days: int=90",
    },
    # ── What-if simulator ───────────────────────────────────────────────────
    "what_if": {
        "desc": "Simulazione what-if: calcola risparmio/costo di una modifica mensile su categoria o totale.",
        "params": "category: str=null, monthly_delta: float=0, monthly_target: float=null, percent_change: float=null, horizon_months: int=12",
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


def _fn_anomalies(db_path: str, params: dict) -> dict:
    """Riusa get_anomalies() senza duplicare la logica statistica."""
    anomalies = get_anomalies()
    if not anomalies:
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Info"],
                "rows": [["Nessuna anomalia rilevata negli ultimi 60 giorni."]],
            },
        }
    top10 = anomalies[:min(10, MAX_CHART_POINTS)]
    chart_data = {
        "type": "bar",
        "data": [{"name": f"{a['description'][:18] or a['category']}", "value": a["amount"]} for a in top10],
        "title": "Top anomalie per z-score (ultimi 60gg)",
    }
    table_data = {
        "headers": ["Data", "Categoria", "Descrizione", "Importo", "Z-score", "% sopra media"],
        "rows": [
            [
                a["date"],
                a["category"],
                a["description"][:40] or "-",
                f"€{a['amount']}",
                str(a["z_score"]),
                f"+{a['pct_above_avg']}%",
            ]
            for a in anomalies[:MAX_TABLE_ROWS]
        ],
    }
    return {"chart_data": chart_data, "table_data": table_data}


def _fn_budget_status(db_path: str, params: dict) -> dict:
    """Stato budget attivi: confronta budgets con spese del mese corrente."""
    ms = _month_start(0)
    rows = _q(
        "SELECT b.category, b.amount AS budget, "
        "COALESCE(SUM(t.amount), 0) AS spent "
        "FROM budgets b "
        "LEFT JOIN transactions t "
        "  ON t.category = b.category AND t.date >= :ms "
        "WHERE b.active = 1 "
        "GROUP BY b.category, b.amount "
        "ORDER BY (COALESCE(SUM(t.amount), 0) / b.amount) DESC "
        "LIMIT :lim",
        {"ms": ms, "lim": MAX_TABLE_ROWS}
    )
    if not rows:
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Info"],
                "rows": [["Nessun budget attivo. Creane uno nella sezione Budget."]],
            },
        }

    table_rows = []
    chart_data_items = []
    for cat, budget, spent in rows:
        budget = round(budget or 0, 2)
        spent  = round(spent  or 0, 2)
        pct    = round(spent / budget * 100, 1) if budget > 0 else 0
        if pct < 80:
            status = "✅ ok"
        elif pct <= 100:
            status = "⚠️ attenzione"
        else:
            status = "🔴 sforato"
        table_rows.append([cat, f"€{budget}", f"€{spent}", f"{pct}%", status])
        chart_data_items.append({"name": cat, "value": pct})

    return {
        "chart_data": {
            "type": "bar",
            "data": chart_data_items[:MAX_CHART_POINTS],
            "title": "Utilizzo budget mese corrente (%)",
        },
        "table_data": {
            "headers": ["Categoria", "Budget", "Speso", "%", "Stato"],
            "rows": table_rows,
        },
    }


def _fn_recurring_vs_variable(db_path: str, params: dict) -> dict:
    """Fisso vs variabile per mese, ultimi period_days giorni."""
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)
    rows = _q(
        "SELECT "
        "  substr(date,1,7) AS month, "
        "  SUM(CASE WHEN is_recurring = 1 THEN amount ELSE 0 END) AS recurring, "
        "  SUM(CASE WHEN is_recurring = 0 OR is_recurring IS NULL THEN amount ELSE 0 END) AS variable "
        "FROM transactions "
        "WHERE date >= :d "
        "GROUP BY month "
        "ORDER BY month DESC "
        "LIMIT :lim",
        {"d": cutoff, "lim": MAX_CHART_POINTS}
    )
    rows = sorted(rows, key=lambda r: r[0])  # ri-ordina ascendente

    table_rows = []
    chart_items = []
    for month, rec, var in rows:
        rec = round(rec or 0, 2)
        var = round(var or 0, 2)
        total = rec + var
        pct_rec = round(rec / total * 100, 1) if total > 0 else 0
        table_rows.append([month, f"€{rec}", f"€{var}", f"{pct_rec}%"])
        chart_items.append({"name": month, "value": rec})   # bar = quota ricorrente

    return {
        "chart_data": {
            "type": "bar",
            "data": chart_items,
            "title": f"Spese ricorrenti per mese (ultimi {period_days}gg)",
        },
        "table_data": {
            "headers": ["Mese", "Ricorrenti", "Variabili", "% Ricorrenti"],
            "rows": table_rows,
        },
    }


def _fn_subscriptions_audit(db_path: str, params: dict) -> dict:
    """Audit abbonamenti: transazioni ricorrenti raggruppate per descrizione+categoria."""
    rows = _q(
        "SELECT description, category, AVG(amount), COUNT(*), MIN(date), MAX(date) "
        "FROM transactions "
        "WHERE is_recurring = 1 "
        "GROUP BY description, category "
        "HAVING COUNT(*) >= 2 "
        "ORDER BY AVG(amount) DESC "
        "LIMIT :lim",
        {"lim": MAX_TABLE_ROWS}
    )
    if not rows:
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Info"],
                "rows": [["Nessun abbonamento ricorrente rilevato (≥2 addebiti)."]],
            },
        }

    table_rows = []
    for desc, cat, avg_amt, count, first, last in rows:
        avg_amt    = round(avg_amt or 0, 2)
        annualized = round(avg_amt * 12, 2)
        table_rows.append([
            desc or "-",
            cat or "-",
            f"€{avg_amt}",
            str(count),
            first or "-",
            last or "-",
            f"€{annualized}",
        ])

    return {
        "chart_data": None,
        "table_data": {
            "headers": ["Descrizione", "Categoria", "Importo medio", "N. addebiti", "Primo", "Ultimo", "Annualizzato"],
            "rows": table_rows,
        },
    }


# ─── ADVANCED ANALYTICS ──────────────────────────────────────────────────────

def _fn_category_volatility(db_path: str, params: dict) -> dict:
    import statistics as _stats
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 180))))
    cutoff = _dates(period_days)
    rows = _q(
        "SELECT category, substr(date,1,7) AS month, SUM(amount) AS monthly_total "
        "FROM transactions WHERE date >= :d "
        "GROUP BY category, month ORDER BY category, month",
        {"d": cutoff}
    )
    cat_months: dict = defaultdict(list)
    for cat, _m, total in rows:
        cat_months[cat].append(total or 0)

    results = []
    for cat, vals in cat_months.items():
        if len(vals) < 2:
            continue
        mean = round(_stats.mean(vals), 2)
        stdev = round(_stats.stdev(vals), 2)
        cv = round(stdev / mean * 100, 1) if mean > 0 else 0
        vol_label = "Alta" if cv > 50 else ("Media" if cv > 25 else "Bassa")
        results.append((cat, mean, stdev, cv, vol_label, len(vals)))

    results.sort(key=lambda x: x[3], reverse=True)
    return {
        "chart_data": {
            "type": "bar",
            "data": [{"name": r[0], "value": r[3]} for r in results[:MAX_CHART_POINTS]],
            "title": f"Volatilità spese per categoria (ultimi {period_days}gg)",
        },
        "table_data": {
            "headers": ["Categoria", "Media mensile", "StdDev", "Volatilità (CV%)", "Mesi"],
            "rows": [
                [r[0], f"€{r[1]}", f"€{r[2]}", f"{r[3]}% — {r[4]}", str(r[5])]
                for r in results[:MAX_TABLE_ROWS]
            ],
        },
    }


def _fn_frequency_analysis(db_path: str, params: dict) -> dict:
    import statistics as _stats
    from datetime import datetime as _dt

    category = params.get("category")
    if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
        category = None
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)

    def _gaps_and_stats(date_list, amount_list):
        gaps = []
        for i in range(1, len(date_list)):
            try:
                d1 = _dt.strptime(date_list[i - 1], "%Y-%m-%d")
                d2 = _dt.strptime(date_list[i], "%Y-%m-%d")
                gaps.append((d2 - d1).days)
            except ValueError:
                pass
        n = len(amount_list)
        mean_amt = round(_stats.mean(amount_list), 2) if amount_list else 0
        median_amt = round(_stats.median(amount_list), 2) if amount_list else 0
        avg_gap = round(_stats.mean(gaps), 1) if gaps else 0
        return n, avg_gap, mean_amt, median_amt, gaps

    if category:
        rows = _q(
            "SELECT date, amount FROM transactions WHERE category = :cat AND date >= :d ORDER BY date",
            {"cat": category, "d": cutoff}
        )
        if not rows:
            return {"chart_data": None, "table_data": {"headers": ["Info"], "rows": [["Nessuna transazione trovata."]]}}
        dates_ = [r[0] for r in rows]
        amounts_ = [r[1] or 0 for r in rows]
        n, avg_gap, mean_amt, median_amt, gaps = _gaps_and_stats(dates_, amounts_)
        chart_items = [
            {"name": dates_[i][5:], "value": gaps[i - 1]}
            for i in range(1, min(len(dates_), MAX_CHART_POINTS + 1))
        ]
        return {
            "chart_data": {"type": "line", "data": chart_items, "title": f"Gap tra transazioni: {category} (giorni)"},
            "table_data": {
                "headers": ["Categoria", "Transazioni", "Gap medio (gg)", "Media €", "Mediana €"],
                "rows": [[category, str(n), str(avg_gap), f"€{mean_amt}", f"€{median_amt}"]],
            },
        }
    else:
        rows = _q(
            "SELECT category, date, amount FROM transactions WHERE date >= :d ORDER BY category, date",
            {"d": cutoff}
        )
        cat_data: dict = defaultdict(lambda: {"amounts": [], "dates": []})
        for cat, date_str, amount in rows:
            cat_data[cat]["amounts"].append(amount or 0)
            cat_data[cat]["dates"].append(date_str)

        table_rows = []
        for cat, data in cat_data.items():
            n, avg_gap, mean_amt, median_amt, _ = _gaps_and_stats(data["dates"], data["amounts"])
            table_rows.append([cat, str(n), str(avg_gap), f"€{mean_amt}", f"€{median_amt}"])
        table_rows.sort(key=lambda r: int(r[1]), reverse=True)
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Categoria", "Transazioni", "Gap medio (gg)", "Media €", "Mediana €"],
                "rows": table_rows[:MAX_TABLE_ROWS],
            },
        }


def _fn_concentration_risk(db_path: str, params: dict) -> dict:
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 30))))
    cutoff = _dates(period_days)
    total = _scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d", {"d": cutoff}) or 0

    cat_rows = _q(
        "SELECT category, SUM(amount) AS s FROM transactions WHERE date >= :d "
        "GROUP BY category ORDER BY s DESC LIMIT 3", {"d": cutoff}
    )
    desc_rows = _q(
        "SELECT COALESCE(description,'?'), SUM(amount) AS s FROM transactions "
        "WHERE date >= :d AND description IS NOT NULL "
        "GROUP BY description ORDER BY s DESC LIMIT 5", {"d": cutoff}
    )
    day_rows = _q(
        "SELECT date, SUM(amount) AS s FROM transactions WHERE date >= :d "
        "GROUP BY date ORDER BY s DESC LIMIT 5", {"d": cutoff}
    )

    def pct(v):
        return f"{round(v / total * 100, 1)}%" if total > 0 else "0%"

    rows: list = (
        [["─── Top 3 categorie ───", "", ""]]
        + [[r[0], f"€{round(r[1],2)}", pct(r[1])] for r in cat_rows]
        + [["─── Top 5 descrizioni ───", "", ""]]
        + [[r[0], f"€{round(r[1],2)}", pct(r[1])] for r in desc_rows]
        + [["─── Top 5 giorni ───", "", ""]]
        + [[r[0], f"€{round(r[1],2)}", pct(r[1])] for r in day_rows]
    )

    top3_total = sum(r[1] for r in cat_rows)
    other = round(total - top3_total, 2)
    chart_items = [{"name": r[0], "value": round(r[1], 2)} for r in cat_rows]
    if other > 0:
        chart_items.append({"name": "Altro", "value": other})

    return {
        "chart_data": {"type": "pie", "data": chart_items, "title": f"Concentrazione spese (ultimi {period_days}gg)"},
        "table_data": {"headers": ["Voce", "Importo", "%"], "rows": rows[:MAX_TABLE_ROWS]},
    }


def _fn_period_compare(db_path: str, params: dict) -> dict:
    period_a_days        = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_a_days", 30))))
    period_b_offset_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_b_offset_days", 30))))

    start_a = _dates(period_a_days)
    end_a   = _dates(0)
    start_b = _dates(period_a_days + period_b_offset_days)
    end_b   = _dates(period_b_offset_days)

    rows_a = _q(
        "SELECT category, SUM(amount) FROM transactions WHERE date >= :s AND date < :e GROUP BY category",
        {"s": start_a, "e": end_a}
    )
    rows_b = _q(
        "SELECT category, SUM(amount) FROM transactions WHERE date >= :s AND date < :e GROUP BY category",
        {"s": start_b, "e": end_b}
    )

    a_map = {r[0]: round(r[1] or 0, 2) for r in rows_a}
    b_map = {r[0]: round(r[1] or 0, 2) for r in rows_b}
    all_cats = sorted(set(a_map) | set(b_map))

    results = []
    for cat in all_cats:
        a = a_map.get(cat, 0)
        b = b_map.get(cat, 0)
        delta_eur = round(a - b, 2)
        delta_pct = round((a - b) / b * 100, 1) if b > 0 else (100.0 if a > 0 else 0.0)
        results.append((cat, a, b, delta_eur, delta_pct))
    results.sort(key=lambda x: abs(x[3]), reverse=True)

    def _fmt_eur(v): return f"+€{v}" if v >= 0 else f"-€{abs(v)}"
    def _fmt_pct(v): return f"+{v}%" if v >= 0 else f"{v}%"

    return {
        "chart_data": {
            "type": "bar",
            "data": [{"name": r[0], "value": r[3]} for r in results[:MAX_CHART_POINTS]],
            "title": f"Delta A({period_a_days}gg) vs B({period_b_offset_days}gg prima)",
        },
        "table_data": {
            "headers": [
                "Categoria",
                f"Periodo A ({period_a_days}gg)",
                f"Periodo B ({period_b_offset_days}gg prima)",
                "Δ€", "Δ%",
            ],
            "rows": [
                [r[0], f"€{r[1]}", f"€{r[2]}", _fmt_eur(r[3]), _fmt_pct(r[4])]
                for r in results[:MAX_TABLE_ROWS]
            ],
        },
    }


def _fn_momentum(db_path: str, params: dict) -> dict:
    from datetime import datetime as _dt

    category = params.get("category")
    if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
        category = None
    period_days = max(14, min(MAX_PERIOD_DAYS, int(params.get("period_days", 60))))
    n_weeks = max(2, period_days // 7)
    cutoff = _dates(period_days)

    def _linear_slope(vals: list) -> float:
        n = len(vals)
        if n < 2:
            return 0.0
        xs = list(range(n))
        sx = sum(xs);  sy = sum(vals)
        sxy = sum(x * y for x, y in zip(xs, vals))
        sxx = sum(x * x for x in xs)
        denom = n * sxx - sx * sx
        return (n * sxy - sx * sy) / denom if denom != 0 else 0.0

    def _classify(pct_week: float) -> str:
        if pct_week > 5:  return "🔴 Accelerazione"
        if pct_week < -5: return "🟢 Decelerazione"
        return "🟡 Stabile"

    def _bucket(rows_iter, base_dt):
        weekly = [0.0] * n_weeks
        for date_str, amt in rows_iter:
            try:
                d = _dt.strptime(date_str, "%Y-%m-%d")
                idx = min((d - base_dt).days // 7, n_weeks - 1)
                weekly[idx] += (amt or 0)
            except ValueError:
                pass
        return weekly

    base = _dt.strptime(cutoff, "%Y-%m-%d")

    if category:
        rows = _q(
            "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d "
            "GROUP BY date ORDER BY date",
            {"cat": category, "d": cutoff}
        )
        weekly = _bucket(rows, base)
        slope = _linear_slope(weekly)
        mean_y = sum(weekly) / n_weeks
        pct_w = round(slope / mean_y * 100, 2) if mean_y else 0.0
        sign = "+" if pct_w >= 0 else ""
        return {
            "chart_data": {
                "type": "line",
                "data": [{"name": f"W{i+1}", "value": round(weekly[i], 2)} for i in range(n_weeks)][:MAX_CHART_POINTS],
                "title": f"Momentum settimanale: {category}",
            },
            "table_data": {
                "headers": ["Categoria", "Trend %/sett", "Classificazione"],
                "rows": [[category, f"{sign}{pct_w}%", _classify(pct_w)]],
            },
        }
    else:
        rows = _q(
            "SELECT category, date, SUM(amount) FROM transactions WHERE date >= :d "
            "GROUP BY category, date ORDER BY category, date",
            {"d": cutoff}
        )
        cat_raw: dict = defaultdict(list)
        for cat, date_str, amt in rows:
            cat_raw[cat].append((date_str, amt))

        table_rows = []
        total_weekly = [0.0] * n_weeks
        for cat, pairs in cat_raw.items():
            weekly = _bucket(pairs, base)
            for i, v in enumerate(weekly):
                total_weekly[i] += v
            slope = _linear_slope(weekly)
            mean_y = sum(weekly) / n_weeks
            pct_w = round(slope / mean_y * 100, 2) if mean_y else 0.0
            sign = "+" if pct_w >= 0 else ""
            table_rows.append([cat, f"{sign}{pct_w}%", _classify(pct_w)])
        table_rows.sort(key=lambda r: float(r[1].replace("%", "")), reverse=True)

        return {
            "chart_data": {
                "type": "line",
                "data": [{"name": f"W{i+1}", "value": round(total_weekly[i], 2)} for i in range(n_weeks)][:MAX_CHART_POINTS],
                "title": "Trend settimanale totale spese",
            },
            "table_data": {
                "headers": ["Categoria", "Trend %/sett", "Classificazione"],
                "rows": table_rows[:MAX_TABLE_ROWS],
            },
        }


# ─── SEARCH & DRILLDOWN ───────────────────────────────────────────────────────

def _fn_search_transactions(db_path: str, params: dict) -> dict:
    import re as _re
    query = _re.sub(r"[^a-zA-Z0-9\s]", "", str(params.get("query", ""))).strip()[:50].lower()
    if not query:
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Info"],
                "rows": [["Query non valida (solo caratteri alfanumerici, max 50 char)."]],
            },
        }
    n = max(1, min(MAX_TOP_N, int(params.get("n", 20))))
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)
    like_q = f"%{query}%"

    rows = _q(
        "SELECT date, category, description, tags, amount FROM transactions "
        "WHERE date >= :d "
        "  AND (LOWER(COALESCE(description,'')) LIKE :q OR LOWER(COALESCE(tags,'')) LIKE :q) "
        "ORDER BY amount DESC LIMIT :n",
        {"d": cutoff, "q": like_q, "n": n}
    )
    if not rows:
        return {
            "chart_data": None,
            "table_data": {"headers": ["Info"], "rows": [[f"Nessuna transazione trovata per '{query}'."]]}
        }

    total_found = sum(r[4] or 0 for r in rows)
    table_rows = [
        [r[0], r[1] or "-", r[2] or "-", r[3] or "-", f"€{round(r[4] or 0, 2)}"]
        for r in rows
    ] + [["── TOTALE ──", "", "", "", f"€{round(total_found, 2)}"]]

    daily = _q(
        "SELECT date, SUM(amount) FROM transactions "
        "WHERE date >= :d "
        "  AND (LOWER(COALESCE(description,'')) LIKE :q OR LOWER(COALESCE(tags,'')) LIKE :q) "
        "GROUP BY date ORDER BY date",
        {"d": cutoff, "q": like_q}
    )
    chart_items = [{"name": r[0][5:], "value": round(r[1] or 0, 2)} for r in daily][:MAX_CHART_POINTS]

    return {
        "chart_data": (
            {"type": "line", "data": chart_items, "title": f"Trend giornaliero: '{query}' ({period_days}gg)"}
            if chart_items else None
        ),
        "table_data": {
            "headers": ["Data", "Categoria", "Descrizione", "Tag", "Importo"],
            "rows": table_rows,
        },
    }


def _fn_category_drill(db_path: str, params: dict) -> dict:
    import statistics as _stats

    category = params.get("category")
    if not isinstance(category, str) or category not in CATEGORIES:
        category = "cibo"
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)

    rows = _q(
        "SELECT date, description, amount FROM transactions WHERE category = :cat AND date >= :d ORDER BY date",
        {"cat": category, "d": cutoff}
    )
    if not rows:
        return {
            "chart_data": None,
            "table_data": {"headers": ["Voce", "Valore", "Extra"], "rows": [[f"Nessuna tx per '{category}'.", "", ""]]},
        }

    amounts = [r[2] or 0 for r in rows]
    total   = round(sum(amounts), 2)
    n       = len(amounts)
    mean    = round(_stats.mean(amounts), 2)
    median  = round(_stats.median(amounts), 2)
    mn, mx  = round(min(amounts), 2), round(max(amounts), 2)

    top_desc = _q(
        "SELECT COALESCE(description,'-'), COUNT(*), SUM(amount) FROM transactions "
        "WHERE category = :cat AND date >= :d AND description IS NOT NULL "
        "GROUP BY description ORDER BY SUM(amount) DESC LIMIT 5",
        {"cat": category, "d": cutoff}
    )
    top_days = _q(
        "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d "
        "GROUP BY date ORDER BY SUM(amount) DESC LIMIT 5",
        {"cat": category, "d": cutoff}
    )

    combined: list = (
        [["─── Statistiche ───", "", ""],
         ["Totale",          f"€{total}", ""],
         ["N. transazioni",  str(n),      ""],
         ["Media",           f"€{mean}",  ""],
         ["Mediana",         f"€{median}",""],
         ["Minima",          f"€{mn}",    ""],
         ["Massima",         f"€{mx}",    ""],
         ["─── Top 5 descrizioni ───", "", ""]]
        + [[d, f"€{round(s,2)}", f"{c} tx"] for d, c, s in top_desc]
        + [["─── Top 5 giorni ───", "", ""]]
        + [[day, f"€{round(s,2)}", ""] for day, s in top_days]
    )

    daily = _q(
        "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d "
        "GROUP BY date ORDER BY date",
        {"cat": category, "d": cutoff}
    )
    chart_items = [{"name": r[0][5:], "value": round(r[1] or 0, 2)} for r in daily][-MAX_CHART_POINTS:]

    return {
        "chart_data": {
            "type": "line",
            "data": chart_items,
            "title": f"Trend giornaliero: {category} (ultimi {period_days}gg)",
        },
        "table_data": {
            "headers": ["Voce", "Valore", "Extra"],
            "rows": combined[:MAX_TABLE_ROWS],
        },
    }


def _fn_tag_analysis(db_path: str, params: dict) -> dict:
    import re as _re

    tag = params.get("tag")
    if tag is not None:
        tag = _re.sub(r"[^a-zA-Z0-9_\s]", "", str(tag))[:30].strip().lower()
        if not tag:
            tag = None
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 90))))
    cutoff = _dates(period_days)

    if tag:
        like_q = f"%{tag}%"
        rows = _q(
            "SELECT date, category, description, amount FROM transactions "
            "WHERE date >= :d AND LOWER(COALESCE(tags,'')) LIKE :q ORDER BY date",
            {"d": cutoff, "q": like_q}
        )
        if not rows:
            return {
                "chart_data": None,
                "table_data": {"headers": ["Info"], "rows": [[f"Nessuna tx con tag '{tag}'."]]}
            }
        total = sum(r[3] or 0 for r in rows)
        table_rows = [
            [r[0], r[1] or "-", r[2] or "-", f"€{round(r[3] or 0, 2)}"]
            for r in rows[: MAX_TABLE_ROWS - 1]
        ] + [["── TOTALE ──", "", "", f"€{round(total, 2)}"]]

        daily = _q(
            "SELECT date, SUM(amount) FROM transactions "
            "WHERE date >= :d AND LOWER(COALESCE(tags,'')) LIKE :q "
            "GROUP BY date ORDER BY date",
            {"d": cutoff, "q": like_q}
        )
        chart_items = [{"name": r[0][5:], "value": round(r[1] or 0, 2)} for r in daily][:MAX_CHART_POINTS]

        return {
            "chart_data": (
                {"type": "line", "data": chart_items, "title": f"Trend tag '{tag}' (ultimi {period_days}gg)"}
                if chart_items else None
            ),
            "table_data": {
                "headers": ["Data", "Categoria", "Descrizione", "Importo"],
                "rows": table_rows,
            },
        }
    else:
        rows = _q(
            "SELECT tags, amount FROM transactions WHERE date >= :d AND tags IS NOT NULL AND tags != ''",
            {"d": cutoff}
        )
        tag_totals: dict = defaultdict(float)
        for tags_str, amount in rows:
            for t in str(tags_str).split(","):
                t = t.strip().lower()
                if t:
                    tag_totals[t] += (amount or 0)

        if not tag_totals:
            return {
                "chart_data": None,
                "table_data": {"headers": ["Info"], "rows": [["Nessun tag trovato nel periodo."]]}
            }

        sorted_tags = sorted(tag_totals.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "chart_data": {
                "type": "bar",
                "data": [{"name": t, "value": round(v, 2)} for t, v in sorted_tags[:MAX_CHART_POINTS]],
                "title": f"Top 10 tag per spesa (ultimi {period_days}gg)",
            },
            "table_data": {
                "headers": ["Tag", "Totale speso"],
                "rows": [[t, f"€{round(v,2)}"] for t, v in sorted_tags],
            },
        }


def _fn_what_if(db_path: str, params: dict) -> dict:
    """What-if simulator: baseline mensile → scenario → risparmio/costo su orizzonte."""
    category = params.get("category")
    if isinstance(category, str) and category not in CATEGORIES:
        category = None
    horizon_months = max(1, min(60, int(params.get("horizon_months", 12))))
    percent_change  = params.get("percent_change")
    monthly_target  = params.get("monthly_target")
    monthly_delta   = float(params.get("monthly_delta", 0))

    cutoff = _dates(90)
    with engine.connect() as conn:
        if category:
            row = conn.execute(
                text("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE date>=:c AND category=:cat"),
                {"c": cutoff, "cat": category},
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE date>=:c"),
                {"c": cutoff},
            ).fetchone()

    total_90 = float(row[0]) if row else 0.0
    baseline = round(total_90 / 3, 2)

    if baseline == 0:
        scope = f"categoria '{category}'" if category else "totale"
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Metrica", "Valore"],
                "rows": [[f"Dati insufficienti per simulare {scope}", "—"]],
            },
        }

    if percent_change is not None:
        new_monthly = round(baseline * (1 + float(percent_change) / 100), 2)
    elif monthly_target is not None:
        new_monthly = round(float(monthly_target), 2)
    else:
        new_monthly = round(baseline + monthly_delta, 2)

    delta_monthly = round(new_monthly - baseline, 2)
    saved_total   = round(-delta_monthly * horizon_months, 2)

    return {
        "chart_data": {
            "type": "bar",
            "title": f"What-if: baseline vs scenario ({horizon_months} mesi)",
            "data": [
                {"name": "Baseline",  "value": round(baseline    * horizon_months, 2)},
                {"name": "Scenario",  "value": round(new_monthly * horizon_months, 2)},
            ],
        },
        "table_data": {
            "headers": ["Metrica", "Baseline", "Scenario"],
            "rows": [
                ["Mensile",                      f"€{baseline}",              f"€{new_monthly}"],
                ["Annuale",                       f"€{round(baseline*12,2)}",  f"€{round(new_monthly*12,2)}"],
                [f"Δ orizzonte ({horizon_months}m)", "—",                     f"€{saved_total:+.2f}"],
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
    "anomalies": _fn_anomalies,
    "budget_status": _fn_budget_status,
    "recurring_vs_variable": _fn_recurring_vs_variable,
    "subscriptions_audit": _fn_subscriptions_audit,
    # Block D — 8 nuove funzioni analitiche
    "category_volatility": _fn_category_volatility,
    "frequency_analysis": _fn_frequency_analysis,
    "concentration_risk": _fn_concentration_risk,
    "period_compare": _fn_period_compare,
    "momentum": _fn_momentum,
    "search_transactions": _fn_search_transactions,
    "category_drill": _fn_category_drill,
    "tag_analysis": _fn_tag_analysis,
    # Block E — What-if simulator
    "what_if": _fn_what_if,
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

SINONIMI CATEGORIA (normalizza sempre):
ristoranti/bar/pizza → cibo | uber/taxi/benzina/metro → trasporti | palestra/medico/farmacia → salute
libri/corso/udemy → formazione | netflix/spotify/prime → abbonamenti | bici/moto/aereo → trasporti

REGOLA MERCHANT: se la domanda cita un brand/negozio/merchant SPECIFICO (nome proprio che NON è
una delle categorie cibo/trasporti/casa/salute/svago/abbigliamento/lavoro/abbonamenti/formazione/altro),
usa search_transactions con params.query = il nome del merchant in minuscolo.
Esempi MERCHANT → search_transactions:
- "quanto ho speso da IKEA?" → search_transactions(query="ikea")
- "spese Amazon" → search_transactions(query="amazon")
- "Starbucks questo mese" → search_transactions(query="starbucks", period_days=30)
- "Uber" (da solo o con contesto) → search_transactions(query="uber")
- "Esselunga sopra i 100€" → search_transactions(query="esselunga")
- "Netflix pagamenti" → search_transactions(query="netflix")
- "benzina Q8" → search_transactions(query="q8")
- "palestra FitActive" → search_transactions(query="fitactive")
- "McDonald's" → search_transactions(query="mcdonald")
- "Trenitalia" → search_transactions(query="trenitalia")

ECCEZIONI — NON usare search_transactions se la domanda è GENERICA (senza merchant specifico):
- "quanto ho speso questo mese?" → summary_stats(period_days=30)
- "quanto ho speso?" → summary_stats(period_days=30)
- "totale spese" → summary_stats o spending_by_category
- "spese di questa settimana" → summary_stats(period_days=7)
- "quanto spendo al mese?" → summary_stats(period_days=30)
- "dimmi quanto spendo" → summary_stats(period_days=30)
REGOLA: se non c'è un nome di brand/negozio nella domanda, NON usare search_transactions.

PERIODO IMPLICITO (mappa queste espressioni al valore period_days corretto):
- "questa settimana" / "questa week" → period_days=7
- "settimana scorsa" → period_days=14
- "questo mese" / "ultimo mese" → period_days=30
- "mese scorso" → usa month_vs_month oppure period_days=60
- "ultimi 2 mesi" → period_days=60
- "ultimi 3 mesi" → period_days=90
- "ultimi 6 mesi" → period_days=180
- "ieri" → period_days=1
- "sempre" / "storico totale" / "da sempre" → period_days=365
Se la domanda contiene "questa settimana" + merchant → search_transactions con period_days=7.

FUNZIONI DISPONIBILI (usa solo i parametri indicati, rispetta i range):
- spending_by_category(period_days=30, range 1..365): "dove vanno i soldi", "analisi completa", "distribuzione spese", "per categoria"
- daily_trend(days=30, range 1..365): "trend giornaliero", "grafico spese nel tempo", "giorno per giorno"
- top_transactions(n=10 range 1..50, category=null, period_days=30 range 1..365): "spese piu' alte", "transazioni piu' costose", "top N"
- month_vs_month(): "confronto mesi", "questo mese vs mese scorso", "variazione mensile"
- spending_by_weekday(period_days=90, range 1..365): "weekend vs feriali", "giorno piu' costoso", "media per giorno settimana"
- category_trend(category, months=6 range 1..24): "andamento [categoria] nel tempo", "storico [categoria] mesi"
- summary_stats(period_days=30, range 1..365): "statistiche generali", "totale e media", "quante transazioni"
- year_end_forecast(): "stima fine anno", "previsione annuale", "quanto spendero' entro dicembre"
- anomalies(): "spese strane", "anomalie", "transazioni fuori dalla norma", "pagamenti insoliti"
- budget_status(): "come vado coi budget", "sto sforando", "stato budget", "budget superato"
- recurring_vs_variable(period_days=90, range 1..365): "fissi vs variabili", "quanto e' ricorrente", "spese fisse"
- subscriptions_audit(): "lista abbonamenti", "audit subscription", "abbonamenti zombie", "ho abbonamenti attivi"
- category_volatility(period_days=180, range 1..365): "variabilita'", "volatilita' di spesa", "categoria piu' imprevedibile", "quanto oscilla"
- frequency_analysis(category=null, period_days=90, range 1..365): "ogni quanto spendo", "frequenza acquisti", "intervallo medio tra transazioni"
- concentration_risk(period_days=30, range 1..365): "concentrazione spese", "dipendo da poche voci", "che concentrazione ho", "dove va la maggior parte"
- period_compare(period_a_days=30 range 1..365, period_b_offset_days=30 range 1..365): "ultime N settimane vs N prima", "confronto due periodi", "come cambiato rispetto a", "delta tra periodi"
- momentum(category=null, period_days=60, range 1..365): "spese in accelerazione", "sto aumentando", "tendenza recente", "il cibo e' in accelerazione"
- search_transactions(query str max50, period_days=90, n=20): "quanto ho speso in [posto]", "trova transazioni con", "cerca [keyword]", "starbucks/esselunga/amazon"
- category_drill(category str, period_days=90, range 1..365): "drilldown [categoria]", "dettaglio [categoria]", "analisi approfondita [categoria]", "breakdown [categoria]"
- tag_analysis(tag=null, period_days=90, range 1..365): "spese taggate [tag]", "analisi tag", "tag [nome]", "cosa ho taggato come"
- what_if(category=null, monthly_delta=0, monthly_target=null, percent_change=null, horizon_months=12): "se taglio X€/mese da [cat]" → {category:cat, monthly_delta:-X}; "se metto budget Y€ su [cat]" → {category:cat, monthly_target:Y}; "se riduco del K% [cat] per N mesi" → {category:cat, percent_change:-K, horizon_months:N}; "quanto risparmio se...", "simulazione"

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

INTERPRET_MULTI_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DOMANDA: {question}

HAI I RISULTATI DI {n_blocks} ANALISI:
{data_summary}

Produci 4-6 frasi che colleghino TRA LORO i blocchi (es. 'la categoria X e' anche quella piu' volatile e contribuisce per il 35% del totale'). NON elencare i blocchi separatamente. Usa numeri ESATTI dai dati. Termina con UNA raccomandazione concreta basata sull'incrocio dei risultati.

Poi 1-2 domande di approfondimento nel campo followup_questions — domande che l'UTENTE farebbe all'AI.
NON includere suggerimenti dentro il campo answer.

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
                    ("period_days",          1,   365,   30),
                    ("days",                 1,   365,   30),
                    ("n",                    1,    50,   10),
                    ("months",               1,    24,    6),
                    ("period_a_days",        1,   365,   30),
                    ("period_b_offset_days", 1,   365,   30),
                    ("horizon_months",       1,    60,   12),
                ]:
                    if key in params:
                        try:
                            params[key] = max(lo, min(hi, int(params[key])))
                        except (ValueError, TypeError):
                            params[key] = default
                # Clip float params to safe ranges
                for key, lo, hi, default in [
                    ("monthly_delta",   -10000, 10000,    0),
                    ("monthly_target",       0, 50000, None),
                    ("percent_change",    -100,  1000, None),
                ]:
                    if key in params and params[key] is not None:
                        try:
                            params[key] = max(lo, min(hi, float(params[key])))
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
                # query: max 50 chars, only alphanum+space
                if "query" in params and params["query"] is not None:
                    import re as _re
                    q = _re.sub(r"[^a-z0-9\s]", "", str(params["query"]).lower()).strip()
                    params["query"] = q[:50] if q else None
                # tag: max 30 chars, only alphanum+underscore
                if "tag" in params and params["tag"] is not None:
                    import re as _re
                    t = _re.sub(r"[^a-z0-9_]", "", str(params["tag"]).lower()).strip()
                    params["tag"] = t[:30] if t else None
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


# ─── MACRO-INTENT ORCHESTRATION ──────────────────────────────────────────────

def _match_macro_intent(question: str) -> "str | None":
    """Keyword match deterministico sui trigger di MACRO_INTENTS. Zero LLM."""
    q = question.lower()
    for intent_name, intent in MACRO_INTENTS.items():
        for trigger in intent["triggers"]:
            if re.search(r"\b" + re.escape(trigger) + r"\b", q):
                return intent_name
    return None


def _build_multi_summary(blocks: list) -> str:
    """Concatena blocchi; tronca proporzionalmente se supera MAX_MULTI_SUMMARY_CHARS."""
    full = "\n\n".join(blocks)
    if len(full) <= MAX_MULTI_SUMMARY_CHARS:
        return full
    truncated = []
    for block in blocks:
        lines = block.splitlines()
        truncated.append("\n".join(lines[:6]))  # header + max 5 data lines
    return "\n\n".join(truncated)[:MAX_MULTI_SUMMARY_CHARS]


def _interpret_multi_results(question: str, data_summary: str, n_blocks: int) -> dict:
    prompt = INTERPRET_MULTI_PROMPT.format(
        n_blocks=n_blocks,
        question=question,
        data_summary=data_summary,
    )
    raw = _llm_call(
        "interpret_multi",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analizza e collega i blocchi."},
        ],
        temperature=0.1,
        max_tokens=600,
        seed=42,
        json_mode=True,
    )
    return _parse_ai_response(raw)


def _execute_macro_intent(question: str, intent_name: str, steps: list) -> dict:
    intent = MACRO_INTENTS[intent_name]
    blocks: list = []
    first_chart = None
    first_table = None

    for fn_name, fn_params in intent["functions"]:
        t = _time.time()
        result = execute_prebuilt_function(fn_name, fn_params)
        cd = result.get("chart_data")
        td = result.get("table_data")
        if first_chart is None and cd is not None:
            first_chart = cd
        if first_table is None and td is not None:
            first_table = td
        header = "## " + fn_name.replace("_", " ").title()
        body   = _format_data_for_interpretation(cd, td)
        blocks.append(f"{header}\n{body}")
        rows = len((cd or {}).get("data", []) or (td or {}).get("rows", []))
        _step(steps, "fn_execute", f"📊 Eseguita {fn_name}", f"{rows} righe DB", t)

    t = _time.time()
    data_summary = _build_multi_summary(blocks)
    interp = _interpret_multi_results(question, data_summary, n_blocks=len(blocks))
    _step(steps, "llm_interpret", "✍️ LLM interpreta i dati (multi)",
          f"{len(data_summary)} char · {len(blocks)} blocchi", t)

    return {
        "answer":             interp.get("answer", "Analisi completata.").strip(),
        "chart_data":         first_chart,
        "data_table":         first_table,
        "followup_questions": interp.get("followup_questions", [])[:MAX_FOLLOWUP_QUESTIONS],
        "reasoning_steps":    steps,
    }


# ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────────

def chat_with_ai(question: str, history=None) -> dict:
    steps: list = []

    # ── Emergency kill-switch ─────────────────────────────────────────────────
    if AI_DISABLE_LLM:
        return {
            "answer": _OUT_OF_SCOPE["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE["followup_questions"],
            "reasoning_steps": steps,
        }

    # PASSO 1 — Pre-filtro lunghezza e input non significativo
    t = _time.time()
    if _input_too_long(question):
        _step(steps, "pre_filter", "⛔ Input troppo lungo",
              f"{len(question)} char > 500", t, "error")
        return {
            "answer": _INPUT_TOO_LONG["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _INPUT_TOO_LONG["followup_questions"],
            "reasoning_steps": steps,
        }
    if _input_meaningless(question):
        _step(steps, "pre_filter", "⛔ Input non significativo",
              f"< 2 caratteri alfabetici", t, "skipped")
        return {
            "answer": _OUT_OF_SCOPE_PREFILTER["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE_PREFILTER["followup_questions"],
            "reasoning_steps": steps,
        }
    _step(steps, "pre_filter", "✓ Lunghezza input OK", f"{len(question)} char", t)

    # PASSO 2 — Pre-filtro OOS deterministico
    t = _time.time()
    if _is_obviously_out_of_scope(question):
        _step(steps, "pre_filter", "⛔ Fuori perimetro (regex)",
              "match: cucina/sport/meteo/codice/news/salute", t, "skipped")
        return {
            "answer": _OUT_OF_SCOPE_PREFILTER["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE_PREFILTER["followup_questions"],
            "reasoning_steps": steps,
        }
    _step(steps, "pre_filter", "✓ In perimetro finanziario", "", t)

    # PASSO 3 — Macro-intent matching (zero LLM)
    t = _time.time()
    macro = _match_macro_intent(question)
    if macro:
        _step(steps, "macro_match", f"⚡ Macro-intent: {macro}",
              f"trigger match → {len(MACRO_INTENTS[macro]['functions'])} funzioni", t)
        return _execute_macro_intent(question, macro, steps)
    _step(steps, "macro_match", "– Nessun macro-intent", "pass-through al router LLM", t)

    # PASSO 4 — Router LLM
    t = _time.time()
    selector = _select_function(question, history)
    use_function = selector.get("use_function")
    in_perimeter = selector.get("in_perimeter", True)
    if not in_perimeter:
        _step(steps, "llm_router", "⛔ LLM: fuori perimetro", "in_perimeter=false", t, "skipped")
        return {
            "answer": _OUT_OF_SCOPE["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE["followup_questions"],
            "reasoning_steps": steps,
        }
    if use_function and isinstance(use_function, dict):
        fn_name    = use_function.get("name", "?")
        fn_params_str = str(use_function.get("params") or {})[:80]
        _step(steps, "llm_router", f"🔀 Router → {fn_name}", f"params: {fn_params_str}", t)
    else:
        _step(steps, "llm_router", "💬 Router → risposta testuale", "nessuna funzione adatta", t)

    # PASSO 5 — Esecuzione funzione + interpret
    if use_function and isinstance(use_function, dict):
        t = _time.time()
        fn_result  = execute_prebuilt_function(
            use_function.get("name", ""), use_function.get("params") or {})
        chart_data = fn_result.get("chart_data")
        table_data = fn_result.get("table_data")
        rows = len((chart_data or {}).get("data", []) or (table_data or {}).get("rows", []))
        _step(steps, "fn_execute", f"📊 Eseguita {use_function.get('name', '')}",
              f"{rows} righe DB", t)

        t = _time.time()
        data_summary = _format_data_for_interpretation(chart_data, table_data)
        interp = _interpret_results(question, data_summary)
        _step(steps, "llm_interpret", "✍️ LLM interpreta i dati",
              f"data_summary: {len(data_summary)} char", t)

        return {
            "answer":             interp.get("answer", "Analisi completata.").strip(),
            "chart_data":         chart_data,
            "data_table":         table_data,
            "followup_questions": interp.get("followup_questions", [])[:MAX_FOLLOWUP_QUESTIONS],
            "reasoning_steps":    steps,
        }

    # PASSO 6 — Risposta testuale
    t = _time.time()
    compact_ctx = build_compact_context()
    interp = _answer_in_perimeter(question, compact_ctx)
    _step(steps, "text_answer", "✍️ LLM risposta testuale",
          f"ctx: {len(compact_ctx)} char", t)

    return {
        "answer":             interp.get("answer", "").strip(),
        "chart_data":         None,
        "data_table":         None,
        "followup_questions": interp.get("followup_questions", [])[:MAX_FOLLOWUP_QUESTIONS],
        "reasoning_steps":    steps,
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
