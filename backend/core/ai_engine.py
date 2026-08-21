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
MODEL = "qwen/qwen3.6-27b"

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

# MACRO_INTENTS rimossi — la selezione multi-funzione è ora delegata all'LLM router.

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
        "reasoning_effort": "none",
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


def _valid_iso_date(s) -> str | None:
    """Valida una stringa data ISO 'YYYY-MM-DD'. Rifiuta formati errati e date future
    oltre oggi (i dati storici non arrivano dal futuro). Ritorna None se non valida."""
    if not isinstance(s, str):
        return None
    try:
        d = date.fromisoformat(s.strip())
    except ValueError:
        return None
    if d > date.today():
        return None
    return d.isoformat()


def _eur(v) -> str:
    """Formatta un importo in euro sempre con 2 decimali (es. 554.0 -> '554.00').
    Fonte unica per evitare incongruenze come '€554.0' vs '€554.00' in tabelle/risposte."""
    try:
        return f"€{float(v or 0):.2f}"
    except (TypeError, ValueError):
        return "€0.00"


def _month_start(months_back: int = 0) -> str:
    """Primo giorno del mese corrente (o N mesi fa)."""
    d = date.today().replace(day=1)
    for _ in range(months_back):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.isoformat()


def build_context(user_id: str) -> str:
    """Costruisce il contesto del DB per il prompt AI — filtrato per user_id."""
    d30 = _dates(30)
    d60 = _dates(60)

    schema = "transactions(id, amount REAL, category TEXT, description TEXT, date TEXT)"
    total_all = _scalar("SELECT COUNT(*) FROM transactions WHERE user_id = :user_id", {"user_id": user_id}) or 0
    date_range = _q("SELECT MIN(date), MAX(date) FROM transactions WHERE user_id = :user_id", {"user_id": user_id})
    dr = date_range[0] if date_range else (None, None)
    grand_total = round(_scalar("SELECT SUM(amount) FROM transactions WHERE user_id = :user_id", {"user_id": user_id}) or 0, 2)

    row = _q("SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d AND date <= :_today AND user_id = :user_id", {"d": d30, "user_id": user_id, "_today": _dates()})
    last_30_total = round(row[0][0] or 0, 2) if row else 0
    last_30_count = row[0][1] or 0 if row else 0

    prev_30 = round(_scalar(
        "SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30 AND user_id = :user_id",
        {"d60": d60, "d30": d30, "user_id": user_id}
    ) or 0, 2)

    cat_30 = _q(
        "SELECT category, COUNT(*), SUM(amount), AVG(amount) FROM transactions "
        "WHERE date >= :d AND date <= :_today AND user_id = :user_id GROUP BY category ORDER BY SUM(amount) DESC",
        {"d": d30, "user_id": user_id, "_today": _dates()}
    )

    total_30_pct = round((last_30_total - prev_30) / prev_30 * 100, 1) if prev_30 > 0 else 0
    trend = f"+{total_30_pct}%" if total_30_pct >= 0 else f"{total_30_pct}%"

    cats_30_str = "\n".join(
        f"  - {c[0]}: {c[1]} tx, {_eur(round(c[2],2))} "
        f"({round(c[2]/last_30_total*100) if last_30_total>0 else 0}% del mese), media {_eur(round(c[3],2))}"
        for c in cat_30
    ) if cat_30 else "  (nessuna transazione)"

    return (
        f"SCHEMA: {schema}\n"
        f"STORICO TOTALE: {total_all} transazioni, {_eur(grand_total)}, range {dr[0]} → {dr[1]}\n"
        f"ULTIMI 30 GIORNI: {_eur(last_30_total)} ({last_30_count} transazioni, {trend} vs mese precedente {_eur(prev_30)})\n"
        f"CATEGORIE ULTIMI 30 GIORNI (usa QUESTI dati per il briefing, NON lo storico):\n{cats_30_str}"
    )


# ─── FUNZIONI PRECONFEZIONATE ─────────────────────────────────────────────────

FUNCTION_CATALOG = {
    "query_spending": {
        "desc": (
            "Funzione universale per spese: totali/statistiche, distribuzione per categoria, "
            "trend giornaliero/mensile, media per giorno della settimana, top N transazioni o "
            "ricerca testuale — tutto tramite parametri, inclusa esclusione categoria. "
            "Usala per QUALSIASI domanda su 'quanto ho speso', 'spese per categoria', 'trend', "
            "'top spese', 'andamento mensile di una categoria', 'media per giorno settimana'."
        ),
        "params": (
            "period_days: int=30, months: int=null (se dato sovrascrive period_days=months*30), "
            "group_by: 'category'|'day'|'weekday'|'month'|'none'=category, "
            "category: str=null (filtro incluso), exclude_category: str=null (filtro escluso), "
            "top_n: int=null (se dato → tabella top N transazioni invece di aggregazione), "
            "search: str=null (se dato → tabella transazioni che matchano il testo, come Ikea/Amazon)"
        ),
    },
    "month_vs_month": {
        "desc": "Confronto spese mese corrente vs precedente per categoria.",
        "params": "(nessuno)",
    },
    "year_end_forecast": {
        "desc": "Proiezione spese fino a fine anno basata sulla media giornaliera recente.",
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


def _fn_query_spending(db_path: str, params: dict) -> dict:
    """Query unificata per spese: aggregazione con filtri periodo/categoria e raggruppamento
    flessibile, oppure elenco transazioni (top N o ricerca testuale). Sostituisce le vecchie
    spending_by_category / summary_stats / daily_trend / spending_by_weekday / category_trend /
    top_transactions: una sola funzione con parametri espliciti invece di 6 funzioni quasi
    identiche tra cui il router doveva indovinare — riduce la superficie di errore del routing."""
    period_days = max(1, min(MAX_PERIOD_DAYS, int(params.get("period_days", 30))))
    months = params.get("months")
    if months is not None:
        try:
            period_days = max(1, min(MAX_PERIOD_DAYS, int(months) * 30))
        except (ValueError, TypeError):
            pass

    group_by = params.get("group_by", "category")
    if group_by not in ("category", "day", "weekday", "month", "none"):
        group_by = "category"

    category = params.get("category")
    if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
        category = None
    exclude_category = params.get("exclude_category")
    if exclude_category is not None and (not isinstance(exclude_category, str) or exclude_category not in CATEGORIES):
        exclude_category = None

    top_n = params.get("top_n")
    search = params.get("search")

    # Range assoluto (date_from/date_to già validate e ordinate da _sanitize_params) ha
    # priorità su period_days/months: una domanda tipo "tra il 14 e il 16 agosto" deve
    # filtrare esattamente quel range, non un numero di giorni relativi a oggi.
    date_from = _valid_iso_date(params.get("date_from"))
    date_to = _valid_iso_date(params.get("date_to"))
    use_absolute_range = bool(date_from and date_to)

    if use_absolute_range:
        cutoff, today = date_from, date_to
    else:
        cutoff, today = _dates(period_days), _dates()

    where = ["date >= :d AND date <= :_today"]
    sql_params: dict = {"d": cutoff, "_today": today}
    if category:
        where.append("category = :cat")
        sql_params["cat"] = category
    if exclude_category:
        where.append("category != :excl")
        sql_params["excl"] = exclude_category
    if search:
        q = re.sub(r"[^a-z0-9\s]", "", str(search).lower()).strip()[:50]
        if q:
            where.append("(LOWER(COALESCE(description,'')) LIKE :q OR LOWER(COALESCE(tags,'')) LIKE :q)")
            sql_params["q"] = f"%{q}%"
    where_sql = " AND ".join(where)

    if use_absolute_range:
        label_bits = [f"dal {cutoff[8:10]}/{cutoff[5:7]}/{cutoff[:4]} al {today[8:10]}/{today[5:7]}/{today[:4]}"]
    else:
        label_bits = [f"ultimi {period_days}gg"]
    if category:
        label_bits.append(f"categoria {category}")
    if exclude_category:
        label_bits.append(f"escl. {exclude_category}")
    label = ", ".join(label_bits)

    # Modalità elenco transazioni: ricerca testuale o top N — forzano una tabella, non un'aggregazione
    if search or top_n:
        n = max(1, min(MAX_TOP_N, int(top_n or 20)))
        rows = _q(
            f"SELECT date, category, description, amount FROM transactions WHERE {where_sql} "
            f"ORDER BY amount DESC LIMIT :n",
            {**sql_params, "n": n}
        )
        return {
            "chart_data": None,
            "table_data": {
                "headers": ["Data", "Categoria", "Descrizione", "Importo"],
                "rows": [[r[0], r[1], r[2] or "-", f"{_eur(round(r[3] or 0, 2))}"] for r in rows],
            },
        }

    if group_by == "category":
        rows = _q(
            f"SELECT category, SUM(amount) FROM transactions WHERE {where_sql} "
            f"GROUP BY category ORDER BY SUM(amount) DESC LIMIT :lim",
            {**sql_params, "lim": MAX_CHART_POINTS}
        )
        data = [{"name": r[0], "value": round(r[1], 2)} for r in rows if r[1] and r[1] > 0]
        return {
            "chart_data": {"type": "bar", "data": data, "title": f"Spese per categoria ({label})"},
            "table_data": None,
        }

    if group_by == "day":
        rows = _q(
            f"SELECT date, SUM(amount) FROM transactions WHERE {where_sql} "
            f"GROUP BY date ORDER BY date DESC LIMIT :lim",
            {**sql_params, "lim": MAX_CHART_POINTS}
        )
        rows = sorted(rows, key=lambda r: r[0])
        data = [{"name": r[0][5:], "value": round(r[1], 2)} for r in rows]
        return {
            "chart_data": {"type": "line", "data": data, "title": f"Trend giornaliero ({label})"},
            "table_data": None,
        }

    if group_by == "weekday":
        from datetime import datetime as _dt
        rows = _q(f"SELECT date, SUM(amount) FROM transactions WHERE {where_sql} GROUP BY date", sql_params)
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
            "chart_data": {"type": "bar", "data": data, "title": f"Media spese per giorno della settimana ({label})"},
            "table_data": None,
        }

    if group_by == "month":
        rows = _q(f"SELECT date, amount FROM transactions WHERE {where_sql} ORDER BY date", sql_params)
        monthly: dict = defaultdict(float)
        for date_str, amount in rows:
            monthly[date_str[:7]] += amount or 0
        sorted_months = sorted(monthly.items())[-MAX_CHART_POINTS:]
        data = [{"name": k, "value": round(v, 2)} for k, v in sorted_months]
        title = f"Andamento mensile: {category}" if category else f"Andamento mensile spese ({label})"
        return {
            "chart_data": {"type": "line", "data": data, "title": title},
            "table_data": None,
        }

    # group_by == "none" → statistiche riassuntive
    row = _q(f"SELECT SUM(amount), COUNT(*), AVG(amount) FROM transactions WHERE {where_sql}", sql_params)
    top_cat = _q(
        f"SELECT category FROM transactions WHERE {where_sql} GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1",
        sql_params
    )
    total, count, avg = (round(row[0][0] or 0, 2), row[0][1] or 0, round(row[0][2] or 0, 2)) if row else (0, 0, 0)
    return {
        "chart_data": None,
        "table_data": {
            "headers": ["Metrica", "Valore"],
            "rows": [
                ["Totale spese", f"{_eur(total)}"],
                ["Transazioni", str(count)],
                ["Media per transazione", f"{_eur(avg)}"],
                ["Categoria top", top_cat[0][0] if top_cat else "-"],
                ["Periodo analizzato", label],
            ],
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
            [r[0], f"{_eur(round(r[1],2))}", f"{_eur(round(r[2],2))}",
             f"+{round((r[1]-r[2])/r[2]*100)}%" if r[2] > 0 else "N/A"]
            for r in rows if (r[1] or 0) > 0 or (r[2] or 0) > 0
        ][:MAX_TABLE_ROWS],
    }
    data = [{"name": r[0], "value": round(r[1], 2)} for r in rows if (r[1] or 0) > 0]
    return {
        "chart_data": {"type": "bar", "data": data, "title": "Spese mese corrente per categoria"},
        "table_data": table,
    }


def _fn_year_end_forecast(db_path: str, params: dict) -> dict:
    today = date.today()
    d30 = _dates(30)
    year_start = today.replace(month=1, day=1).isoformat()

    total_30 = round(_scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d AND date <= :_today", {"d": d30, "_today": _dates()}) or 0, 2)
    spent_ytd = round(_scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d AND date <= :_today", {"d": year_start, "_today": _dates()}) or 0, 2)

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
                ["Speso da inizio anno", f"{_eur(spent_ytd)}"],
                ["Media giornaliera (ultimi 30gg)", f"{_eur(daily_avg)}"],
                ["Giorni rimasti all'anno", str(days_remaining)],
                ["Previsto per il resto dell'anno", f"{_eur(projected_remaining)}"],
                ["Totale proiettato anno", f"{_eur(projected_total)}"],
            ],
        },
    }


def _fn_budget_status(db_path: str, params: dict) -> dict:
    """Stato budget attivi: confronta budgets con spese del mese corrente."""
    ms = _month_start(0)
    rows = _q(
        "SELECT b.category, b.amount AS budget, "
        "COALESCE(SUM(t.amount), 0) AS spent "
        "FROM budgets b "
        "LEFT JOIN transactions t "
        "  ON t.category = b.category AND t.date >= :ms AND t.date <= :_today "
        "WHERE b.active = 1 "
        "GROUP BY b.category, b.amount "
        "ORDER BY (COALESCE(SUM(t.amount), 0) / b.amount) DESC "
        "LIMIT :lim",
        {"ms": ms, "lim": MAX_TABLE_ROWS, "_today": _dates()}
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
        table_rows.append([cat, f"{_eur(budget)}", f"{_eur(spent)}", f"{pct}%", status])
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
        "WHERE date >= :d AND date <= :_today "
        "GROUP BY month "
        "ORDER BY month DESC "
        "LIMIT :lim",
        {"d": cutoff, "lim": MAX_CHART_POINTS, "_today": _dates()}
    )
    rows = sorted(rows, key=lambda r: r[0])  # ri-ordina ascendente

    table_rows = []
    chart_items = []
    for month, rec, var in rows:
        rec = round(rec or 0, 2)
        var = round(var or 0, 2)
        total = rec + var
        pct_rec = round(rec / total * 100, 1) if total > 0 else 0
        table_rows.append([month, f"{_eur(rec)}", f"{_eur(var)}", f"{pct_rec}%"])
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
            f"{_eur(avg_amt)}",
            str(count),
            first or "-",
            last or "-",
            f"{_eur(annualized)}",
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
        "FROM transactions WHERE date >= :d AND date <= :_today "
        "GROUP BY category, month ORDER BY category, month",
        {"d": cutoff, "_today": _dates()}
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
                [r[0], f"{_eur(r[1])}", f"{_eur(r[2])}", f"{r[3]}% — {r[4]}", str(r[5])]
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
            "SELECT date, amount FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today ORDER BY date",
            {"cat": category, "d": cutoff, "_today": _dates()}
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
                "rows": [[category, str(n), str(avg_gap), f"{_eur(mean_amt)}", f"{_eur(median_amt)}"]],
            },
        }
    else:
        rows = _q(
            "SELECT category, date, amount FROM transactions WHERE date >= :d AND date <= :_today ORDER BY category, date",
            {"d": cutoff, "_today": _dates()}
        )
        cat_data: dict = defaultdict(lambda: {"amounts": [], "dates": []})
        for cat, date_str, amount in rows:
            cat_data[cat]["amounts"].append(amount or 0)
            cat_data[cat]["dates"].append(date_str)

        table_rows = []
        for cat, data in cat_data.items():
            n, avg_gap, mean_amt, median_amt, _ = _gaps_and_stats(data["dates"], data["amounts"])
            table_rows.append([cat, str(n), str(avg_gap), f"{_eur(mean_amt)}", f"{_eur(median_amt)}"])
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
    total = _scalar("SELECT SUM(amount) FROM transactions WHERE date >= :d AND date <= :_today", {"d": cutoff, "_today": _dates()}) or 0

    cat_rows = _q(
        "SELECT category, SUM(amount) AS s FROM transactions WHERE date >= :d AND date <= :_today "
        "GROUP BY category ORDER BY s DESC LIMIT 3", {"d": cutoff, "_today": _dates()}
    )
    desc_rows = _q(
        "SELECT COALESCE(description,'?'), SUM(amount) AS s FROM transactions "
        "WHERE date >= :d AND date <= :_today AND description IS NOT NULL "
        "GROUP BY description ORDER BY s DESC LIMIT 5", {"d": cutoff, "_today": _dates()}
    )
    day_rows = _q(
        "SELECT date, SUM(amount) AS s FROM transactions WHERE date >= :d AND date <= :_today "
        "GROUP BY date ORDER BY s DESC LIMIT 5", {"d": cutoff, "_today": _dates()}
    )

    def pct(v):
        return f"{round(v / total * 100, 1)}%" if total > 0 else "0%"

    rows: list = (
        [["─── Top 3 categorie ───", "", ""]]
        + [[r[0], f"{_eur(round(r[1],2))}", pct(r[1])] for r in cat_rows]
        + [["─── Top 5 descrizioni ───", "", ""]]
        + [[r[0], f"{_eur(round(r[1],2))}", pct(r[1])] for r in desc_rows]
        + [["─── Top 5 giorni ───", "", ""]]
        + [[r[0], f"{_eur(round(r[1],2))}", pct(r[1])] for r in day_rows]
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

    def _fmt_eur(v): return f"+{_eur(v)}" if v >= 0 else f"-{_eur(abs(v))}"
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
                [r[0], f"{_eur(r[1])}", f"{_eur(r[2])}", _fmt_eur(r[3]), _fmt_pct(r[4])]
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
            "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today "
            "GROUP BY date ORDER BY date",
            {"cat": category, "d": cutoff, "_today": _dates()}
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
            "SELECT category, date, SUM(amount) FROM transactions WHERE date >= :d AND date <= :_today "
            "GROUP BY category, date ORDER BY category, date",
            {"d": cutoff, "_today": _dates()}
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
        "WHERE date >= :d AND date <= :_today "
        "  AND (LOWER(COALESCE(description,'')) LIKE :q OR LOWER(COALESCE(tags,'')) LIKE :q) "
        "ORDER BY amount DESC LIMIT :n",
        {"d": cutoff, "q": like_q, "n": n, "_today": _dates()}
    )
    if not rows:
        return {
            "chart_data": None,
            "table_data": {"headers": ["Info"], "rows": [[f"Nessuna transazione trovata per '{query}'."]]}
        }

    total_found = sum(r[4] or 0 for r in rows)
    table_rows = [
        [r[0], r[1] or "-", r[2] or "-", r[3] or "-", f"{_eur(round(r[4] or 0, 2))}"]
        for r in rows
    ] + [["── TOTALE ──", "", "", "", f"{_eur(round(total_found, 2))}"]]

    daily = _q(
        "SELECT date, SUM(amount) FROM transactions "
        "WHERE date >= :d AND date <= :_today "
        "  AND (LOWER(COALESCE(description,'')) LIKE :q OR LOWER(COALESCE(tags,'')) LIKE :q) "
        "GROUP BY date ORDER BY date",
        {"d": cutoff, "q": like_q, "_today": _dates()}
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
        "SELECT date, description, amount FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today ORDER BY date",
        {"cat": category, "d": cutoff, "_today": _dates()}
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
        "WHERE category = :cat AND date >= :d AND date <= :_today AND description IS NOT NULL "
        "GROUP BY description ORDER BY SUM(amount) DESC LIMIT 5",
        {"cat": category, "d": cutoff, "_today": _dates()}
    )
    top_days = _q(
        "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today "
        "GROUP BY date ORDER BY SUM(amount) DESC LIMIT 5",
        {"cat": category, "d": cutoff, "_today": _dates()}
    )

    combined: list = (
        [["─── Statistiche ───", "", ""],
         ["Totale",          f"{_eur(total)}", ""],
         ["N. transazioni",  str(n),      ""],
         ["Media",           f"{_eur(mean)}",  ""],
         ["Mediana",         f"{_eur(median)}",""],
         ["Minima",          f"{_eur(mn)}",    ""],
         ["Massima",         f"{_eur(mx)}",    ""],
         ["─── Top 5 descrizioni ───", "", ""]]
        + [[d, f"{_eur(round(s,2))}", f"{c} tx"] for d, c, s in top_desc]
        + [["─── Top 5 giorni ───", "", ""]]
        + [[day, f"{_eur(round(s,2))}", ""] for day, s in top_days]
    )

    daily = _q(
        "SELECT date, SUM(amount) FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today "
        "GROUP BY date ORDER BY date",
        {"cat": category, "d": cutoff, "_today": _dates()}
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
            "WHERE date >= :d AND date <= :_today AND LOWER(COALESCE(tags,'')) LIKE :q ORDER BY date",
            {"d": cutoff, "q": like_q, "_today": _dates()}
        )
        if not rows:
            return {
                "chart_data": None,
                "table_data": {"headers": ["Info"], "rows": [[f"Nessuna tx con tag '{tag}'."]]}
            }
        total = sum(r[3] or 0 for r in rows)
        table_rows = [
            [r[0], r[1] or "-", r[2] or "-", f"{_eur(round(r[3] or 0, 2))}"]
            for r in rows[: MAX_TABLE_ROWS - 1]
        ] + [["── TOTALE ──", "", "", f"{_eur(round(total, 2))}"]]

        daily = _q(
            "SELECT date, SUM(amount) FROM transactions "
            "WHERE date >= :d AND date <= :_today AND LOWER(COALESCE(tags,'')) LIKE :q "
            "GROUP BY date ORDER BY date",
            {"d": cutoff, "q": like_q, "_today": _dates()}
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
            "SELECT tags, amount FROM transactions WHERE date >= :d AND date <= :_today AND tags IS NOT NULL AND tags != ''",
            {"d": cutoff, "_today": _dates()}
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
                "rows": [[t, f"{_eur(round(v,2))}"] for t, v in sorted_tags],
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
                text("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE date>=:c AND date <= :_today AND category=:cat"),
                {"c": cutoff, "cat": category, "_today": _dates()},
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE date>=:c AND date <= :_today"),
                {"c": cutoff, "_today": _dates()},
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
                ["Mensile",                      f"{_eur(baseline)}",              f"{_eur(new_monthly)}"],
                ["Annuale",                       f"{_eur(round(baseline*12,2))}",  f"{_eur(round(new_monthly*12,2))}"],
                [f"Δ orizzonte ({horizon_months}m)", "—",                     f"€{saved_total:+.2f}"],
            ],
        },
    }


_PREBUILT_FUNCTIONS = {
    "query_spending": _fn_query_spending,
    "month_vs_month": _fn_month_vs_month,
    "year_end_forecast": _fn_year_end_forecast,
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

FUNCTION_SELECTOR_PROMPT = """Sei il router di FinCopilot. Analizza la domanda e scegli le funzioni da chiamare.

REGOLA PRINCIPALE: puoi scegliere 1, 2 o 3 funzioni (max 3).
- 1 funzione → domanda specifica ("quanto ho speso da Ikea?", "top 10 spese", "trend del cibo")
- 2-3 funzioni → domanda genuinamente larga che richiede analisi combinate per una risposta ricca
- 0 funzioni + in_perimeter=true → domanda finanziaria valida ma nessuna funzione la copre

ESEMPI MULTI-FUNZIONE (2-3 funzioni):
- "come sto andando?" → [query_spending(period_days=30, group_by="category"), month_vs_month()]
- "fammi un'analisi completa" → [query_spending(period_days=30, group_by="category"), month_vs_month(), recurring_vs_variable()]
- "dove posso risparmiare?" → [subscriptions_audit(), concentration_risk()]
- "analisi del trend generale" → [query_spending(period_days=60, group_by="day"), momentum(), month_vs_month()]
- "panoramica finanziaria" → [query_spending(period_days=30, group_by="category"), month_vs_month(), budget_status()]

ESEMPI MONO-FUNZIONE (1 funzione):
- "top 10 spese" → [query_spending(top_n=10)]
- "quanto ho speso da Ikea?" → [query_spending(search="ikea")]
- "trend del cibo" → [query_spending(category="cibo", months=6, group_by="month")]
- "stato budget" → [budget_status()]
- "quanto ho speso questo mese?" → [query_spending(period_days=30, group_by="none")]
- "quanto ho speso negli ultimi 3 giorni?" → [query_spending(period_days=3, group_by="none")]
- "quanto ho speso questo mese escludendo la categoria casa?" → [query_spending(period_days=30, group_by="none", exclude_category="casa")]
- "spese per categoria di questo mese senza abbonamenti" → [query_spending(period_days=30, group_by="category", exclude_category="abbonamenti")]
- "togliendo le spese per la casa questo mese quanto ho speso?" → [query_spending(period_days=30, group_by="none", exclude_category="casa")]
- "media spese per giorno della settimana" → [query_spending(period_days=90, group_by="weekday")]

SINONIMI CATEGORIA (normalizza sempre):
ristoranti/bar/pizza → cibo | uber/taxi/benzina/metro → trasporti | palestra/medico/farmacia → salute
libri/corso/udemy → formazione | netflix/spotify/prime → abbonamenti | bici/moto/aereo → trasporti

REGOLA MERCHANT: se la domanda cita un brand/negozio SPECIFICO (nome proprio NON uguale a una
categoria), usa query_spending con params.search = il nome in minuscolo.
Esempi: "IKEA"→search="ikea", "Amazon"→search="amazon", "Starbucks"→search="starbucks",
"Esselunga"→search="esselunga", "Q8"→search="q8", "FitActive"→search="fitactive",
"McDonald's"→search="mcdonald", "Trenitalia"→search="trenitalia", "Netflix pagamenti"→search="netflix"

ECCEZIONI — NON usare search per domande GENERICHE (senza merchant specifico):
- "quanto ho speso questo mese?" → query_spending(period_days=30, group_by="none")
- "totale spese" → query_spending(group_by="none") o query_spending(group_by="category")
- "spese di questa settimana" → query_spending(period_days=7, group_by="none")

PERIODO IMPLICITO (relativo a oggi — __TODAY__):
- "questa settimana" → period_days=7 | "questo mese" → period_days=30
- "ultimi 2 mesi" → period_days=60 | "ultimi 3 mesi" → period_days=90
- "ultimi 6 mesi" → period_days=180 | "ieri" → period_days=1
- "sempre" / "storico" → period_days=365 | nessun periodo → usa il default
- "ultimi N giorni" (qualsiasi N, es. "ultimi 3 giorni", "ultimi 10 giorni") → period_days=N esatto,
  scegli SEMPRE query_spending, MAI 0 funzioni per questo tipo di domanda

PERIODO ASSOLUTO — la domanda cita date/un range specifico invece che "ultimi N giorni/mesi":
- Se la domanda specifica un range di date esplicito ("tra il 14 e il 16 agosto", "dal 3 al 10
  luglio", "nel weekend del 5-6 luglio", "il 20 agosto"), NON usare period_days/months: calcola
  le date ISO esatte (YYYY-MM-DD) e passa query_spending(date_from=..., date_to=...).
  Per una singola data, date_from = date_to = quella data.
- Anno: se non specificato usa l'anno corrente (oggi è __TODAY__). Se il giorno/mese risultante
  cade nel futuro rispetto a oggi, usa l'anno precedente invece (l'utente si riferisce sempre al
  passato quando chiede "quanto ho speso").
- Esempi (oggi = __TODAY__):
  - "quanto ho speso tra il 14 e il 16 agosto?" → query_spending(date_from="__TODAY_YEAR__-08-14", date_to="__TODAY_YEAR__-08-16", group_by="none")
  - "spese del 20 luglio" → query_spending(date_from="__TODAY_YEAR__-07-20", date_to="__TODAY_YEAR__-07-20", group_by="none")
  - "dal 1 al 15 giugno per categoria" → query_spending(date_from="__TODAY_YEAR__-06-01", date_to="__TODAY_YEAR__-06-15", group_by="category")
- CONTINUITÀ CONVERSAZIONALE: se la domanda è un follow-up implicito su un range di date appena
  discusso nel turno precedente ("mostrami l'elenco completo", "quali sono i dettagli", "e per
  categoria X in quel periodo?"), riusa LO STESSO date_from/date_to del turno precedente — non
  tornare a period_days di default. Se serve solo l'elenco delle transazioni invece di
  un'aggregazione, usa query_spending con lo stesso date_from/date_to più top_n (es. top_n=50)
  così la tabella elenca le righe invece di aggregarle.

ESCLUSIONE/INCLUSIONE CATEGORIA — ragiona sul SIGNIFICATO, non su parole chiave:
- Se l'utente vuole il totale/statistiche CON una categoria esclusa dal computo (qualunque sia la
  formulazione — "escludendo X", "togliendo X", "senza X", "tolta X", "al netto di X", "a parte X",
  o varianti equivalenti), passa params.exclude_category = X (stessa normalizzazione sinonimi).
- Il calcolo dell'esclusione è sempre fatto lato funzione (SQL) con UNA SOLA chiamata a
  query_spending — non stimarlo o ricalcolarlo mai nel testo della risposta finale sottraendo
  numeri di due chiamate diverse.

FUNZIONI DISPONIBILI (rispetta i range indicati):
- query_spending(period_days=30 range 1..365, months=null range 1..24, date_from=null "YYYY-MM-DD",
  date_to=null "YYYY-MM-DD", group_by="category"|"day"|"weekday"|"month"|"none",
  category=null, exclude_category=null, top_n=null range 1..50, search=null): funzione universale
  per spese — usala per QUALSIASI domanda su totali, distribuzione per categoria, trend, top spese,
  andamento mensile di una categoria, media per giorno settimana o ricerca merchant. Se date_from
  E date_to sono entrambe valorizzate hanno priorità su period_days/months (vedi PERIODO ASSOLUTO).
- month_vs_month(): confronto mese corrente vs precedente per categoria
- year_end_forecast(): proiezione spese fine anno da media giornaliera
- budget_status(): stato budget attivi con semaforo ok/warning/exceeded
- recurring_vs_variable(period_days=90, range 1..365): fissi vs variabili per mese
- subscriptions_audit(): abbonamenti ricorrenti con costo annualizzato
- category_volatility(period_days=180, range 1..365): volatilità mensile per categoria (CV%)
- frequency_analysis(category=null, period_days=90, range 1..365): frequenza e gap medio tra acquisti
- concentration_risk(period_days=30, range 1..365): top3 categorie e top5 descrizioni per peso %
- period_compare(period_a_days=30 range 1..365, period_b_offset_days=30 range 1..365): delta tra due finestre
- momentum(category=null, period_days=60, range 1..365): regressione lineare settimanale — trend %/settimana
- search_transactions(query str max50, period_days=90, n=20): ricerca LIKE su descrizione+tag
- category_drill(category str, period_days=90, range 1..365): drilldown completo di una categoria
- tag_analysis(tag=null, period_days=90, range 1..365): analisi per tag
- what_if(category=null, monthly_delta=0, monthly_target=null, percent_change=null, horizon_months=12): simulazione risparmio

CASO OOS — domanda NON finanziaria (cucina, sport, meteo, codice, salute generica, meta-AI):
{"reasoning": "...", "use_functions": [], "in_perimeter": false}

Prima di scegliere le funzioni, compila SEMPRE il campo "reasoning" con 1 frase breve che spiega
cosa hai capito della domanda: periodo richiesto, eventuale categoria da includere/escludere, e
perché hai scelto quelle funzioni. Ragiona sul senso della domanda, non su parole chiave isolate.

Rispondi SOLO con JSON valido, niente testo extra:
{"reasoning": "...", "use_functions": [{"name": "...", "params": {...}}, ...], "in_perimeter": true}"""

INTERPRET_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DOMANDA: {question}

DATI:
{data_summary}

Scrivi una risposta breve e SCANSIONABILE, non un paragrafo lungo — deve leggersi in 5 secondi su
schermo piccolo. Struttura ESATTA del campo "answer" (markdown):
1. Una riga di apertura (max 1 frase) con il numero/pattern più importante.
2. Un elenco puntato (righe che iniziano con "- ") di massimo 4 punti, uno per dato/categoria
   rilevante — ogni punto breve, non una frase completa.
3. Una riga finale in **grassetto** con 1 raccomandazione concreta.

REGOLE:
- Usa numeri ESATTI dai dati (importi, nomi, date)
- NON fare calcoli aritmetici (somme, sottrazioni, percentuali) di tua iniziativa: riporta SOLO
  i valori già presenti nei dati, così come sono. Se i dati non contengono già il numero che serve
  per rispondere, dillo invece di stimarlo o ricalcolarlo tu.
- Identifica il pattern principale o l'anomalia piu' interessante
- NON dire "la tabella mostra", "ecco i dati" — analizza direttamente
- Usa **grassetto** per cifre o categorie chiave nei punti elenco
- NON scrivere un unico paragrafo di prosa continua

Poi 1-2 domande di approfondimento nel campo followup_questions — domande che l'UTENTE farebbe all'AI.
Esempi corretti: "Mostrami il trend dell'abbigliamento negli ultimi 6 mesi", "Quali sono le 5 spese piu' alte di trasporti?"
NON includere suggerimenti di domande dentro il campo answer. Il campo answer contiene SOLO l'analisi.

SOLO JSON: {{"answer": "...", "followup_questions": ["...", "..."]}}"""

INTERPRET_MULTI_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DOMANDA: {question}

HAI I RISULTATI DI {n_blocks} ANALISI:
{data_summary}

Scrivi una risposta breve e SCANSIONABILE, non un paragrafo lungo — deve leggersi in pochi secondi
su schermo piccolo. Struttura ESATTA del campo "answer" (markdown):
1. Una riga di apertura (max 1 frase) che collega i blocchi tra loro (es. "la categoria X è anche
   quella più volatile e contribuisce per il 35% del totale").
2. Un elenco puntato (righe che iniziano con "- ") di massimo 4-5 punti con gli incroci/pattern più
   rilevanti tra i blocchi — NON elencare i blocchi separatamente, ogni punto deve collegare dati.
3. Una riga finale in **grassetto** con UNA raccomandazione concreta basata sull'incrocio dei risultati.

Usa numeri ESATTI dai dati, senza fare calcoli aritmetici (somme, sottrazioni, percentuali) di tua
iniziativa: riporta solo i valori già presenti nei blocchi. NON scrivere un unico paragrafo di prosa continua.

Poi 1-2 domande di approfondimento nel campo followup_questions — domande che l'UTENTE farebbe all'AI.
NON includere suggerimenti dentro il campo answer.

SOLO JSON: {{"answer": "...", "followup_questions": ["...", "..."]}}"""

TEXT_ANSWER_PROMPT = """Sei FinCopilot, consulente finanziario personale. Rispondi in italiano.

DATI UTENTE (ultimi 30gg):
{compact_context}

Rispondi in modo breve e SCANSIONABILE, non un paragrafo lungo — deve leggersi in pochi secondi su
schermo piccolo. Struttura del campo "answer" (markdown):
1. Una riga di apertura (max 1 frase) che risponde direttamente alla domanda.
2. Se citi più di 1-2 numeri/dati, usa un elenco puntato (righe che iniziano con "- "), un punto per
   dato — MAI un paragrafo unico che li elenca in prosa. Se citi al massimo 1-2 numeri, salta l'elenco.
3. Se dai un consiglio, chiudi con una riga in **grassetto** con la raccomandazione concreta.
REGOLE:
- Usa i numeri dal contesto quando utile
- Sii diretto e pratico, dai consigli concreti
- Usa **grassetto** per cifre o concetti chiave (mai lasciare ** non chiuso)
- Se non hai dati sufficienti per rispondere con certezza, dillo chiaramente
- NON scrivere un unico paragrafo di prosa continua

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

def _sanitize_params(name: str, params: dict) -> dict:
    """Sanitizza i parametri di una singola funzione prebuilt (clip + whitelist)."""
    params = dict(params)
    for key, lo, hi, default in [
        ("period_days",          1,   365,   30),
        ("days",                 1,   365,   30),
        ("n",                    1,    50,   10),
        ("top_n",                1,    50,   10),
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
    if "chart_type" in params:
        if params["chart_type"] not in ("bar", "line"):
            params["chart_type"] = "bar"
    if "category" in params and params["category"] is not None:
        cat = params["category"]
        if not isinstance(cat, str) or cat not in CATEGORIES:
            params["category"] = None
    if "exclude_category" in params and params["exclude_category"] is not None:
        excl = params["exclude_category"]
        if not isinstance(excl, str) or excl not in CATEGORIES:
            params["exclude_category"] = None
    if "query" in params and params["query"] is not None:
        q = re.sub(r"[^a-z0-9\s]", "", str(params["query"]).lower()).strip()
        params["query"] = q[:50] if q else None
    if "search" in params and params["search"] is not None:
        s = re.sub(r"[^a-z0-9\s]", "", str(params["search"]).lower()).strip()
        params["search"] = s[:50] if s else None
    if "group_by" in params:
        if params["group_by"] not in ("category", "day", "weekday", "month", "none"):
            params["group_by"] = "category"
    if "tag" in params and params["tag"] is not None:
        t = re.sub(r"[^a-z0-9_]", "", str(params["tag"]).lower()).strip()
        params["tag"] = t[:30] if t else None
    if "date_from" in params or "date_to" in params:
        d_from = _valid_iso_date(params.get("date_from"))
        d_to = _valid_iso_date(params.get("date_to"))
        # Range assoluto valido solo se ENTRAMBI gli estremi sono date reali — un solo estremo
        # valido è ambiguo (periodo aperto non supportato dalle funzioni) e va scartato invece
        # di produrre silenziosamente un filtro sbagliato.
        if d_from and d_to:
            if d_from > d_to:
                d_from, d_to = d_to, d_from
            params["date_from"], params["date_to"] = d_from, d_to
        else:
            params["date_from"] = params["date_to"] = None
    return params


def _validate_router_output(parsed: dict) -> dict:
    """Valida l'output del router LLM: produce use_functions (lista, max 3) + in_perimeter."""
    # Retrocompatibilità: se il modello restituisce ancora la shape singola
    if "use_function" in parsed and "use_functions" not in parsed:
        uf = parsed.get("use_function")
        parsed["use_functions"] = [uf] if uf else []

    use_functions = parsed.get("use_functions", [])
    in_perimeter  = bool(parsed.get("in_perimeter", True))
    reasoning     = parsed.get("reasoning", "")
    if not isinstance(reasoning, str):
        reasoning = ""

    if not isinstance(use_functions, list):
        use_functions = []

    validated = []
    for fn in use_functions:
        if not isinstance(fn, dict):
            continue
        name = fn.get("name", "")
        if name not in _PREBUILT_FUNCTIONS:
            if _DEBUG_LOG_ROUTING:
                logger.debug("ROUTER invalid function name=%r — discarded", name)
            continue
        params = fn.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        validated.append({"name": name, "params": _sanitize_params(name, params)})

    return {
        "use_functions": validated[:3],
        "in_perimeter":  in_perimeter,
        "reasoning":     reasoning,
    }


# ─── CORE AI FUNCTIONS ────────────────────────────────────────────────────────

def _format_data_for_interpretation(chart_data, table_data) -> str:
    parts = []
    if chart_data:
        parts.append(f"Grafico '{chart_data.get('title', '')}' ({chart_data.get('type', 'bar')}):")
        for item in chart_data.get("data", [])[:MAX_DATA_SUMMARY_ROWS]:
            parts.append(f"  {item.get('name')}: {_eur(item.get('value'))}")
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
    row = _q("SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d AND date <= :_today", {"d": d30, "_today": _dates()})
    total = round(row[0][0] or 0, 2) if row else 0
    count = row[0][1] or 0 if row else 0
    prev = round(_scalar(
        "SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30",
        {"d60": d60, "d30": d30}
    ) or 0, 2)
    cats = _q(
        "SELECT category, SUM(amount) FROM transactions WHERE date >= :d AND date <= :_today "
        "GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5",
        {"d": d30, "_today": _dates()}
    )
    trend = f"+{round((total-prev)/prev*100,1)}%" if prev > 0 else "N/D"
    cats_str = ", ".join(f"{c[0]} {_eur(round(c[1],2))}" for c in cats)
    return f"Totale 30gg: {_eur(total)} ({count} tx, {trend} vs mese prec.) | Top categorie: {cats_str}"


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


def _render_function_selector_prompt() -> str:
    """Inietta la data odierna nel prompt del router (placeholder testuali, non .format(),
    perché il prompt contiene JSON letterale con parentesi graffe che .format() romperebbe)."""
    today = date.today()
    return (
        FUNCTION_SELECTOR_PROMPT
        .replace("__TODAY_YEAR__", str(today.year))
        .replace("__TODAY__", today.isoformat())
    )


def _select_function(question: str, history) -> dict:
    messages = [{"role": "system", "content": _render_function_selector_prompt()}]
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
        max_tokens=350,
        seed=42,
        json_mode=True,
    )

    parsed = _parse_ai_response(raw)
    validated = _validate_router_output(parsed)

    if _DEBUG_LOG_ROUTING:
        logger.debug("ROUTER raw=%r  validated=%r", raw[:200], validated)

    return validated


def _interpret_results(question: str, data_summary: str,
                       prompt_override: str = None) -> dict:
    base = prompt_override or INTERPRET_PROMPT
    prompt = base.format(question=question, data_summary=data_summary)
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


# ─── MULTI-FUNCTION ORCHESTRATION ────────────────────────────────────────────

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
              "< 2 caratteri alfabetici", t, "skipped")
        return {
            "answer": _OUT_OF_SCOPE_PREFILTER["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE_PREFILTER["followup_questions"],
            "reasoning_steps": steps,
        }
    _step(steps, "pre_filter", "✓ Lunghezza input OK", f"{len(question)} char", t)

    # PASSO 2 — Pre-filtro OOS deterministico (regex, zero LLM)
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

    # PASSO 3 — Router LLM: restituisce use_functions (lista 0..3)
    t = _time.time()
    selector      = _select_function(question, history)
    use_functions = selector.get("use_functions", [])
    in_perimeter  = selector.get("in_perimeter", True)

    if not in_perimeter:
        _step(steps, "llm_router", "⛔ LLM: fuori perimetro",
              selector.get("reasoning") or "in_perimeter=false", t, "skipped")
        return {
            "answer": _OUT_OF_SCOPE["answer"],
            "chart_data": None,
            "data_table": None,
            "followup_questions": _OUT_OF_SCOPE["followup_questions"],
            "reasoning_steps": steps,
        }

    if not use_functions:
        # Nessuna funzione adatta → risposta testuale con contesto compatto
        _step(steps, "llm_router", "💬 Router → risposta testuale",
              selector.get("reasoning") or "nessuna funzione selezionata", t)
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

    # 1..3 funzioni selezionate dal router
    fn_names = [f["name"] for f in use_functions]
    n = len(use_functions)
    router_reasoning = selector.get("reasoning", "")
    _step(steps, "llm_router",
          f"🔀 Router → {', '.join(fn_names)}",
          router_reasoning or f"{n} funzion{'e' if n == 1 else 'i'}",
          t)

    # PASSO 4 — Esecuzione di tutte le funzioni selezionate
    results: list = []
    first_chart = None
    first_table = None
    for fn in use_functions:
        t = _time.time()
        result = execute_prebuilt_function(fn["name"], fn["params"])
        cd = result.get("chart_data")
        td = result.get("table_data")
        if first_chart is None and cd is not None:
            first_chart = cd
        if first_table is None and td is not None:
            first_table = td
        rows = len((cd or {}).get("data", []) or (td or {}).get("rows", []))
        _step(steps, "fn_execute", f"📊 {fn['name']}", f"{rows} righe", t)
        results.append((fn["name"], result))

    # PASSO 5 — Interpretazione (singola o multi-blocco)
    t = _time.time()
    if len(results) == 1:
        _, fn_result = results[0]
        data_summary = _format_data_for_interpretation(
            fn_result.get("chart_data"), fn_result.get("table_data")
        )
        interp = _interpret_results(question, data_summary)
    else:
        blocks = []
        for name, res in results:
            header = "## " + name.replace("_", " ").title()
            body   = _format_data_for_interpretation(res.get("chart_data"), res.get("table_data"))
            blocks.append(f"{header}\n{body}")
        data_summary = _build_multi_summary(blocks)
        interp = _interpret_multi_results(question, data_summary, n_blocks=len(results))

    _step(steps, "llm_interpret",
          f"✍️ LLM interpreta ({len(results)} blocch{'o' if len(results) == 1 else 'i'})",
          f"{len(data_summary)} char", t)

    return {
        "answer":             interp.get("answer", "Analisi completata.").strip(),
        "chart_data":         first_chart,
        "data_table":         first_table,
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


def generate_briefing(user_id: str) -> dict:
    import time
    now = time.time()
    # Per-user cache key: use (user_id, timestamp)
    cache_key = (user_id, "briefing")
    if cache_key not in _briefing_cache:
        _briefing_cache[cache_key] = {"data": None, "ts": 0}

    cache_entry = _briefing_cache[cache_key]
    if cache_entry["data"] and (now - cache_entry["ts"]) < 3600:
        return cache_entry["data"]

    context = build_context(user_id)
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
            cache_entry["data"] = result
            cache_entry["ts"] = now
            return result
    except Exception:
        pass

    return {
        "insights": [
            {"title": "Dati caricati", "body": "Il tuo storico e' disponibile per l'analisi.", "type": "info"},
        ],
        "action": "Fai una domanda nella chat per analizzare le tue spese.",
    }


def _percentile(data: list, p: float) -> float:
    s = sorted(data)
    n = len(s)
    if n == 0:
        return 0.0
    idx = (p / 100) * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def get_anomalies() -> list:
    import statistics as _stats

    d60 = _dates(60)
    d90 = _dates(90)
    d7  = _dates(7)
    all_anomalies: list = []

    # ── TIPO 1: amount_spike ───────────────────────────────────────────────
    rows60 = _q(
        "SELECT id, amount, category, description, date, time FROM transactions "
        "WHERE date >= :d AND date <= :_today ORDER BY date DESC",
        {"d": d60, "_today": _dates()},
    )
    by_cat: dict = defaultdict(list)
    for row in rows60:
        by_cat[row[2]].append(row)

    for cat, cat_rows in by_cat.items():
        if len(cat_rows) < 3:
            continue
        amounts = [r[1] for r in cat_rows]
        mean  = _stats.mean(amounts)
        stdev = _stats.stdev(amounts) if len(amounts) > 1 else 0.0
        if stdev == 0:
            continue
        p75 = _percentile(amounts, 75)
        p90 = _percentile(amounts, 90)
        med = _percentile(amounts, 50)
        mn, mx = min(amounts), max(amounts)
        for row in cat_rows:
            z = (row[1] - mean) / stdev
            if z > 2.0:
                pct_above = round((row[1] - mean) / mean * 100) if mean > 0 else 0
                severity = "high" if z > 3.0 else "medium"
                all_anomalies.append({
                    "id": row[0],
                    "amount": round(row[1], 2),
                    "category": cat,
                    "description": row[3] or "",
                    "date": row[4],
                    "time": row[5],
                    "z_score": round(z, 2),
                    "avg_category": round(mean, 2),
                    "pct_above_avg": pct_above,
                    "detection_type": "amount_spike",
                    "detection_label": f"Importo €{row[1]:.2f} su {cat}: +{pct_above}% sopra la media ({z:.1f}σ)",
                    "severity": severity,
                    "stats": {
                        "mean": round(mean, 2),
                        "median": round(med, 2),
                        "p75": round(p75, 2),
                        "p90": round(p90, 2),
                        "std": round(stdev, 2),
                        "z_score": round(z, 2),
                        "sample_size": len(amounts),
                        "min": round(mn, 2),
                        "max": round(mx, 2),
                    },
                })

    # ── TIPO 2: new_merchant ───────────────────────────────────────────────
    recent_tx = _q(
        "SELECT id, amount, category, description, date, time FROM transactions "
        "WHERE date >= :d AND date <= :_today AND amount > 10 AND description IS NOT NULL "
        "AND description != '' ORDER BY date DESC",
        {"d": d60, "_today": _dates()},
    )
    for row in recent_tx:
        desc = (row[3] or "").strip()
        if not desc:
            continue
        count = _scalar(
            "SELECT COUNT(*) FROM transactions WHERE description = :desc AND date < :tx_date",
            {"desc": desc, "tx_date": row[4]},
        ) or 0
        if count == 0:
            all_anomalies.append({
                "id": row[0],
                "amount": round(row[1], 2),
                "category": row[2],
                "description": desc,
                "date": row[4],
                "time": row[5],
                "z_score": 0.0,
                "avg_category": 0.0,
                "pct_above_avg": 0,
                "detection_type": "new_merchant",
                "detection_label": f"Primo acquisto mai registrato: {desc}",
                "severity": "low",
                "stats": {"first_seen": row[4], "category": row[2]},
            })

    # ── TIPO 3: frequency_spike ────────────────────────────────────────────
    cat_60 = _q(
        "SELECT category, COUNT(*) FROM transactions WHERE date >= :d AND date <= :_today GROUP BY category",
        {"d": d60, "_today": _dates()},
    )
    cat_7 = _q(
        "SELECT category, COUNT(*) FROM transactions WHERE date >= :d AND date <= :_today GROUP BY category",
        {"d": d7, "_today": _dates()},
    )
    cat_60_map = {r[0]: r[1] for r in cat_60}
    cat_7_map  = {r[0]: r[1] for r in cat_7}

    for cat, count_week in cat_7_map.items():
        total_60 = cat_60_map.get(cat, 0)
        if total_60 < 3:
            continue
        avg_weekly = total_60 / 8.0
        if count_week > max(2, avg_weekly * 2):
            rep = _q(
                "SELECT id, amount, category, description, date, time FROM transactions "
                "WHERE category = :cat AND date >= :d AND date <= :_today ORDER BY date DESC LIMIT 1",
                {"cat": cat, "d": d7, "_today": _dates()},
            )
            if not rep:
                continue
            r = rep[0]
            ratio = round(count_week / avg_weekly, 1) if avg_weekly > 0 else 0.0
            severity = "high" if count_week > avg_weekly * 3 else "medium"
            all_anomalies.append({
                "id": r[0],
                "amount": round(r[1], 2),
                "category": cat,
                "description": r[3] or "",
                "date": r[4],
                "time": r[5],
                "z_score": 0.0,
                "avg_category": 0.0,
                "pct_above_avg": 0,
                "detection_type": "frequency_spike",
                "detection_label": f"{count_week} transazioni in {cat} questa settimana (media: {avg_weekly:.1f}/sett)",
                "severity": severity,
                "stats": {
                    "count_this_week": count_week,
                    "avg_weekly": round(avg_weekly, 1),
                    "ratio": ratio,
                    "category": cat,
                },
            })

    # ── TIPO 4: duplicate_suspect ──────────────────────────────────────────
    dup_rows = _q(
        "SELECT id, amount, category, description, date, time FROM transactions "
        "WHERE date >= :d AND date <= :_today AND description IS NOT NULL AND description != '' "
        "ORDER BY description, amount, date",
        {"d": d90, "_today": _dates()},
    )
    dup_groups: dict = defaultdict(list)
    for row in dup_rows:
        key = (row[3].lower().strip(), round(row[1], 2))
        dup_groups[key].append(row)

    from datetime import datetime as _dt
    for key, group in dup_groups.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda r: r[4])
        for i in range(len(group_sorted) - 1):
            r1, r2 = group_sorted[i], group_sorted[i + 1]
            try:
                d1 = _dt.fromisoformat(r1[4])
                d2 = _dt.fromisoformat(r2[4])
                hours_apart = abs((d2 - d1).total_seconds()) / 3600
                if hours_apart <= 48:
                    severity = "high" if hours_apart <= 2 else ("medium" if hours_apart <= 24 else "low")
                    all_anomalies.append({
                        "id": r2[0],
                        "amount": round(r2[1], 2),
                        "category": r2[2],
                        "description": r2[3] or "",
                        "date": r2[4],
                        "time": r2[5],
                        "z_score": 0.0,
                        "avg_category": 0.0,
                        "pct_above_avg": 0,
                        "detection_type": "duplicate_suspect",
                        "detection_label": f"Possibile duplicato: {r2[3]} €{r2[1]:.2f} già registrato {hours_apart:.0f}h prima",
                        "severity": severity,
                        "stats": {
                            "original_date": r1[4],
                            "original_time": r1[5],
                            "hours_apart": round(hours_apart, 1),
                            "original_tx_id": r1[0],
                            "amount": round(r2[1], 2),
                        },
                    })
            except Exception:
                continue

    # ── TIPO 5: unusual_time ───────────────────────────────────────────────
    time_rows = _q(
        "SELECT id, amount, category, description, date, time FROM transactions "
        "WHERE date >= :d AND date <= :_today AND time IS NOT NULL ORDER BY date DESC",
        {"d": d60, "_today": _dates()},
    )
    by_cat_time: dict = defaultdict(list)
    for row in time_rows:
        if row[5]:
            by_cat_time[row[2]].append(row)

    for cat, cat_time_rows in by_cat_time.items():
        if len(cat_time_rows) < 10:
            continue
        hist_hours_rows = _q(
            "SELECT time FROM transactions WHERE category = :cat "
            "AND time IS NOT NULL ORDER BY date DESC LIMIT 50",
            {"cat": cat},
        )
        hours = []
        for hr in hist_hours_rows:
            try:
                hours.append(int(hr[0].split(":")[0]))
            except Exception:
                continue
        if len(hours) < 10:
            continue
        usual_start = int(_percentile(hours, 10))
        usual_end   = int(_percentile(hours, 90))
        for row in cat_time_rows:
            try:
                tx_hour = int(row[5].split(":")[0])
            except Exception:
                continue
            if tx_hour < usual_start - 1 or tx_hour > usual_end + 1:
                all_anomalies.append({
                    "id": row[0],
                    "amount": round(row[1], 2),
                    "category": cat,
                    "description": row[3] or "",
                    "date": row[4],
                    "time": row[5],
                    "z_score": 0.0,
                    "avg_category": 0.0,
                    "pct_above_avg": 0,
                    "detection_type": "unusual_time",
                    "detection_label": (
                        f"Transazione {cat} alle {row[5]}, "
                        f"fuori dall'orario abituale ({usual_start:02d}:00–{usual_end:02d}:00)"
                    ),
                    "severity": "low",
                    "stats": {
                        "tx_time": row[5],
                        "usual_start": f"{usual_start:02d}:00",
                        "usual_end": f"{usual_end:02d}:00",
                        "category": cat,
                        "sample_size": len(hours),
                    },
                })

    # ── SORT (severity ASC, date DESC within group) + CAP ─────────────────
    _sev = {"high": 0, "medium": 1, "low": 2}
    all_anomalies.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_anomalies.sort(key=lambda x: _sev.get(x.get("severity", "low"), 2))
    return all_anomalies[:20]


def get_anomaly_detail(tx_id: int, detection_type: str, user_id: str):
    import statistics as _stats

    row = _q(
        "SELECT id, amount, category, description, date, time FROM transactions WHERE id = :id AND user_id = :user_id",
        {"id": tx_id, "user_id": user_id},
    )
    if not row:
        return None
    tx = row[0]
    tx_dict = {
        "id": tx[0], "amount": round(tx[1], 2), "category": tx[2],
        "description": tx[3] or "", "date": tx[4], "time": tx[5],
    }

    d60 = _dates(60)
    d7  = _dates(7)

    if detection_type == "amount_spike":
        cat_rows = _q(
            "SELECT amount FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today AND user_id = :user_id",
            {"cat": tx[2], "d": d60, "user_id": user_id, "_today": _dates()},
        )
        amounts = [r[0] for r in cat_rows]
        if len(amounts) < 2:
            stats = {}
        else:
            mean  = _stats.mean(amounts)
            stdev = _stats.stdev(amounts)
            z = (tx[1] - mean) / stdev if stdev > 0 else 0.0
            stats = {
                "mean": round(mean, 2), "median": round(_percentile(amounts, 50), 2),
                "p75": round(_percentile(amounts, 75), 2),
                "p90": round(_percentile(amounts, 90), 2),
                "std": round(stdev, 2), "z_score": round(z, 2),
                "sample_size": len(amounts),
                "min": round(min(amounts), 2), "max": round(max(amounts), 2),
            }
        ctx = _q(
            "SELECT date, amount, description FROM transactions "
            "WHERE category = :cat AND user_id = :user_id ORDER BY date DESC LIMIT 10",
            {"cat": tx[2], "user_id": user_id},
        )
        context = [{"date": r[0], "amount": round(r[1], 2), "description": r[2] or ""} for r in ctx]

    elif detection_type == "new_merchant":
        stats = {"first_seen": tx[4], "category": tx[2]}
        ctx = _q(
            "SELECT date, amount, description FROM transactions "
            "WHERE category = :cat AND user_id = :user_id ORDER BY date DESC LIMIT 5",
            {"cat": tx[2], "user_id": user_id},
        )
        context = [{"date": r[0], "amount": round(r[1], 2), "description": r[2] or ""} for r in ctx]

    elif detection_type == "frequency_spike":
        count_7 = _scalar(
            "SELECT COUNT(*) FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today AND user_id = :user_id",
            {"cat": tx[2], "d": d7, "user_id": user_id, "_today": _dates()},
        ) or 0
        count_60 = _scalar(
            "SELECT COUNT(*) FROM transactions WHERE category = :cat AND date >= :d AND date <= :_today AND user_id = :user_id",
            {"cat": tx[2], "d": d60, "user_id": user_id, "_today": _dates()},
        ) or 0
        avg_weekly = round(count_60 / 8.0, 1)
        ratio = round(count_7 / avg_weekly, 1) if avg_weekly > 0 else 0.0
        stats = {
            "count_this_week": count_7, "avg_weekly": avg_weekly,
            "ratio": ratio, "category": tx[2],
        }
        ctx = _q(
            "SELECT date, amount, description FROM transactions "
            "WHERE category = :cat AND date >= :d AND date <= :_today AND user_id = :user_id ORDER BY date DESC",
            {"cat": tx[2], "d": d7, "user_id": user_id, "_today": _dates()},
        )
        context = [{"date": r[0], "amount": round(r[1], 2), "description": r[2] or ""} for r in ctx]

    elif detection_type == "duplicate_suspect":
        # Find the original tx (same description+amount, earlier date)
        orig = _q(
            "SELECT id, date, time, amount FROM transactions "
            "WHERE description = :desc AND ABS(amount - :amt) < 0.02 AND date < :tx_date AND user_id = :user_id "
            "ORDER BY date DESC LIMIT 1",
            {"desc": tx[3] or "", "amt": tx[1], "tx_date": tx[4], "user_id": user_id},
        )
        if orig:
            o = orig[0]
            from datetime import datetime as _dt2
            try:
                hours_apart = abs((_dt2.fromisoformat(tx[4]) - _dt2.fromisoformat(o[1])).total_seconds()) / 3600
            except Exception:
                hours_apart = 0.0
            stats = {
                "original_tx_id": o[0], "original_date": o[1], "original_time": o[2],
                "hours_apart": round(hours_apart, 1), "amount": round(tx[1], 2),
            }
        else:
            stats = {"amount": round(tx[1], 2)}
        ctx = _q(
            "SELECT date, amount, description FROM transactions "
            "WHERE (description = :desc AND ABS(amount - :amt) < 0.02 AND user_id = :user_id) "
            "ORDER BY date DESC LIMIT 5",
            {"desc": tx[3] or "", "amt": tx[1], "user_id": user_id},
        )
        context = [{"date": r[0], "amount": round(r[1], 2), "description": r[2] or ""} for r in ctx]

    elif detection_type == "unusual_time":
        hist = _q(
            "SELECT time FROM transactions WHERE category = :cat "
            "AND time IS NOT NULL AND user_id = :user_id ORDER BY date DESC LIMIT 50",
            {"cat": tx[2], "user_id": user_id},
        )
        hours = []
        for h in hist:
            try:
                hours.append(int(h[0].split(":")[0]))
            except Exception:
                continue
        usual_start = int(_percentile(hours, 10)) if hours else 0
        usual_end   = int(_percentile(hours, 90)) if hours else 23
        stats = {
            "tx_time": tx[5] or "", "category": tx[2],
            "usual_start": f"{usual_start:02d}:00",
            "usual_end": f"{usual_end:02d}:00",
            "sample_size": len(hours),
        }
        ctx = _q(
            "SELECT date, amount, description FROM transactions "
            "WHERE category = :cat AND time IS NOT NULL AND user_id = :user_id ORDER BY date DESC LIMIT 5",
            {"cat": tx[2], "user_id": user_id},
        )
        context = [{"date": r[0], "amount": round(r[1], 2), "description": r[2] or ""} for r in ctx]

    else:
        stats = {}
        context = []

    return {"tx": tx_dict, "detection_type": detection_type, "stats": stats, "context": context}


# ─── IN-MEMORY ANOMALY CACHE ───────────────────────────────────────────────
# Cache structure: {user_id: {(year, month): result_dict}}
# Survives during session, lost on server restart (acceptable for MVP)
_anomaly_cache: dict = {}


def _count_anomalies_by_type(anomalies: list) -> dict:
    """Count anomalies by detection_type."""
    counts: dict = {}
    for anomaly in anomalies:
        dt = anomaly.get("detection_type", "amount_spike")
        counts[dt] = counts.get(dt, 0) + 1
    return counts


def _detect_anomalies_for_transactions(txs: list) -> list:
    """
    Apply all 5 detectors to a list of transaction rows.
    Rows format: (id, amount, category, description, date, time)
    Returns list of anomaly dicts.
    """
    import statistics as _stats
    from datetime import datetime as _dt

    all_anomalies: list = []

    if not txs:
        return all_anomalies

    # ── TIPO 1: amount_spike ───────────────────────────────────────────────
    by_cat: dict = defaultdict(list)
    for row in txs:
        by_cat[row[2]].append(row)

    for cat, cat_rows in by_cat.items():
        if len(cat_rows) < 3:
            continue
        amounts = [r[1] for r in cat_rows]
        mean = _stats.mean(amounts)
        stdev = _stats.stdev(amounts) if len(amounts) > 1 else 0.0
        if stdev == 0:
            continue
        p75 = _percentile(amounts, 75)
        p90 = _percentile(amounts, 90)
        med = _percentile(amounts, 50)
        mn, mx = min(amounts), max(amounts)
        for row in cat_rows:
            z = (row[1] - mean) / stdev
            if z > 2.0:
                pct_above = round((row[1] - mean) / mean * 100) if mean > 0 else 0
                severity = "high" if z > 3.0 else "medium"
                all_anomalies.append({
                    "id": row[0],
                    "amount": round(row[1], 2),
                    "category": cat,
                    "description": row[3] or "",
                    "date": row[4],
                    "time": row[5],
                    "z_score": round(z, 2),
                    "avg_category": round(mean, 2),
                    "pct_above_avg": pct_above,
                    "detection_type": "amount_spike",
                    "detection_label": f"Importo €{row[1]:.2f} su {cat}: +{pct_above}% sopra la media ({z:.1f}σ)",
                    "severity": severity,
                    "stats": {
                        "mean": round(mean, 2),
                        "median": round(med, 2),
                        "p75": round(p75, 2),
                        "p90": round(p90, 2),
                        "std": round(stdev, 2),
                        "z_score": round(z, 2),
                        "sample_size": len(amounts),
                        "min": round(mn, 2),
                        "max": round(mx, 2),
                    },
                })

    # ── TIPO 2: new_merchant ───────────────────────────────────────────────
    for row in txs:
        desc = (row[3] or "").strip()
        if not desc or row[1] <= 10:
            continue
        # Count previous occurrences in DB (simple approach: not in current txs)
        count = _scalar(
            "SELECT COUNT(*) FROM transactions WHERE description = :desc AND date < :tx_date",
            {"desc": desc, "tx_date": row[4]},
        ) or 0
        if count == 0:
            all_anomalies.append({
                "id": row[0],
                "amount": round(row[1], 2),
                "category": row[2],
                "description": desc,
                "date": row[4],
                "time": row[5],
                "z_score": 0.0,
                "avg_category": 0.0,
                "pct_above_avg": 0,
                "detection_type": "new_merchant",
                "detection_label": f"Primo acquisto mai registrato: {desc}",
                "severity": "low",
                "stats": {"first_seen": row[4], "category": row[2]},
            })

    # ── TIPO 3: frequency_spike ────────────────────────────────────────────
    # Count transactions by category in this period and compare to 60 days
    cat_period = {}
    for row in txs:
        cat = row[2]
        cat_period[cat] = cat_period.get(cat, 0) + 1

    # Get 60-day baseline for each category
    d60 = _dates(60)
    cat_60_rows = _q(
        "SELECT category, COUNT(*) FROM transactions WHERE date >= :d AND date <= :_today GROUP BY category",
        {"d": d60, "_today": _dates()},
    )
    cat_60_map = {r[0]: r[1] for r in cat_60_rows}

    # Period is typically 30-31 days, so avg_weekly = count_60 / 8.0
    for cat, count_period in cat_period.items():
        total_60 = cat_60_map.get(cat, 0)
        if total_60 < 3:
            continue
        avg_weekly = total_60 / 8.0
        # If period count is > 2x weekly average, flag it
        if count_period > max(2, avg_weekly * 2):
            # Get the most recent tx of this category
            rep = [r for r in txs if r[2] == cat]
            if rep:
                r = rep[0]
                ratio = round(count_period / avg_weekly, 1) if avg_weekly > 0 else 0.0
                severity = "high" if count_period > avg_weekly * 3 else "medium"
                all_anomalies.append({
                    "id": r[0],
                    "amount": round(r[1], 2),
                    "category": cat,
                    "description": r[3] or "",
                    "date": r[4],
                    "time": r[5],
                    "z_score": 0.0,
                    "avg_category": 0.0,
                    "pct_above_avg": 0,
                    "detection_type": "frequency_spike",
                    "detection_label": f"{count_period} transazioni in {cat} questo mese (media: {avg_weekly:.1f}/sett)",
                    "severity": severity,
                    "stats": {
                        "count_this_period": count_period,
                        "avg_weekly": round(avg_weekly, 1),
                        "ratio": ratio,
                        "category": cat,
                    },
                })

    # ── TIPO 4: duplicate_suspect ──────────────────────────────────────────
    dup_groups: dict = defaultdict(list)
    for row in txs:
        if not (row[3] and row[3].strip()):
            continue
        key = (row[3].lower().strip(), round(row[1], 2))
        dup_groups[key].append(row)

    for key, group in dup_groups.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda r: r[4])
        for i in range(len(group_sorted) - 1):
            r1, r2 = group_sorted[i], group_sorted[i + 1]
            try:
                d1 = _dt.fromisoformat(r1[4])
                d2 = _dt.fromisoformat(r2[4])
                hours_apart = abs((d2 - d1).total_seconds()) / 3600
                if hours_apart <= 48:
                    severity = "high" if hours_apart <= 2 else ("medium" if hours_apart <= 24 else "low")
                    all_anomalies.append({
                        "id": r2[0],
                        "amount": round(r2[1], 2),
                        "category": r2[2],
                        "description": r2[3] or "",
                        "date": r2[4],
                        "time": r2[5],
                        "z_score": 0.0,
                        "avg_category": 0.0,
                        "pct_above_avg": 0,
                        "detection_type": "duplicate_suspect",
                        "detection_label": f"Possibile duplicato: {r2[3]} €{r2[1]:.2f} già registrato {hours_apart:.0f}h prima",
                        "severity": severity,
                        "stats": {
                            "original_date": r1[4],
                            "original_time": r1[5],
                            "hours_apart": round(hours_apart, 1),
                            "original_tx_id": r1[0],
                            "amount": round(r2[1], 2),
                        },
                    })
            except Exception:
                continue

    # ── TIPO 5: unusual_time ───────────────────────────────────────────────
    by_cat_time: dict = defaultdict(list)
    for row in txs:
        if row[5]:
            by_cat_time[row[2]].append(row)

    # Get historical hours for each category
    for cat, cat_time_rows in by_cat_time.items():
        hist_hours_rows = _q(
            "SELECT time FROM transactions WHERE category = :cat "
            "AND time IS NOT NULL ORDER BY date DESC LIMIT 50",
            {"cat": cat},
        )
        hours = []
        for hr in hist_hours_rows:
            try:
                hours.append(int(hr[0].split(":")[0]))
            except Exception:
                continue
        if len(hours) < 10:
            continue
        usual_start = int(_percentile(hours, 10))
        usual_end = int(_percentile(hours, 90))
        for row in cat_time_rows:
            try:
                tx_hour = int(row[5].split(":")[0])
            except Exception:
                continue
            if tx_hour < usual_start - 1 or tx_hour > usual_end + 1:
                all_anomalies.append({
                    "id": row[0],
                    "amount": round(row[1], 2),
                    "category": cat,
                    "description": row[3] or "",
                    "date": row[4],
                    "time": row[5],
                    "z_score": 0.0,
                    "avg_category": 0.0,
                    "pct_above_avg": 0,
                    "detection_type": "unusual_time",
                    "detection_label": (
                        f"Transazione {cat} alle {row[5]}, "
                        f"fuori dall'orario abituale ({usual_start:02d}:00–{usual_end:02d}:00)"
                    ),
                    "severity": "low",
                    "stats": {
                        "tx_time": row[5],
                        "usual_start": f"{usual_start:02d}:00",
                        "usual_end": f"{usual_end:02d}:00",
                        "category": cat,
                        "sample_size": len(hours),
                    },
                })

    # Sort: severity (high→low) then date (desc)
    _sev = {"high": 0, "medium": 1, "low": 2}
    all_anomalies.sort(key=lambda x: x.get("date", ""), reverse=True)
    all_anomalies.sort(key=lambda x: _sev.get(x.get("severity", "low"), 2))
    
    # Deduplica: se stessa transazione triggera più anomalie, tieni la più grave
    unique_anomalies = {}
    for a in all_anomalies:
        tx_id = a["id"]
        if tx_id not in unique_anomalies:
            unique_anomalies[tx_id] = a
        else:
            # Se già presente, tieni quella con severity più alta (già ordinata)
            pass
            
    return list(unique_anomalies.values())[:20]


def get_anomalies_for_month(
    user_id: str,
    year: int,
    month: int,
    force_refresh: bool = False,
) -> dict:
    """
    FUNZIONE UNICA per ottenere anomalie di un mese.
    Usata da dashboard, report, endpoint refresh.
    """
    from datetime import datetime
    from calendar import monthrange

    cache_key = (year, month)

    # Hit cache
    if not force_refresh and user_id in _anomaly_cache:
        if cache_key in _anomaly_cache[user_id]:
            return _anomaly_cache[user_id][cache_key]

    # Cache miss: ricalcola
    first_day = date(year, month, 1)
    last_day = date(year, month, monthrange(year, month)[1])

    rows = _q(
        "SELECT id, amount, category, description, date, time FROM transactions "
        "WHERE date >= :first AND date <= :last "
        "ORDER BY date DESC",
        {"first": first_day.isoformat(), "last": last_day.isoformat()},
    )

    anomalies = _detect_anomalies_for_transactions(rows)

    # Costruisci response unica
    result = {
        "anomalies": anomalies,
        "count": len(anomalies),
        "by_type": _count_anomalies_by_type(anomalies),
        "generated_at": datetime.now().isoformat(),
    }

    # Salva in cache
    if user_id not in _anomaly_cache:
        _anomaly_cache[user_id] = {}
    _anomaly_cache[user_id][cache_key] = result
    
    return result


def invalidate_anomaly_cache(
    user_id: str,
    year: int = None,
    month: int = None,
) -> None:
    """
    Invalida cache per un utente.
    Se year/month specificati, invalida solo quel mese.
    Altrimenti invalida tutto per l'utente.
    """
    if user_id not in _anomaly_cache:
        return

    if year is not None and month is not None:
        cache_key = (year, month)
        _anomaly_cache[user_id].pop(cache_key, None)
    else:
        _anomaly_cache[user_id] = {}

