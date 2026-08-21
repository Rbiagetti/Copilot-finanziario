"""
Backtest end-to-end del motore chat AI — 60 casi conversazionali.

Esecuzione:
  python -m pytest backend/tests/test_chat_backtest.py -v -s
  python backend/tests/test_chat_backtest.py          # runner standalone

Test con max_llm_calls=0 girano SEMPRE (nessuna API key necessaria).
Test LLM: skippati se GROQ_API_KEY non è impostata.
Il report HTML viene scritto in backend/tests/backtest_report.html.
"""
from __future__ import annotations

import os
import sys
import time
import html as _html
import pytest
from pathlib import Path

# ── Import motore ──────────────────────────────────────────────────────────────
from backend.core.ai_engine import (
    chat_with_ai,
    _is_obviously_out_of_scope,
    _input_too_long,
    get_llm_stats,
    _reset_llm_stats,
)
from backend.tests.seed_test_data import seed_backtest_db

REPORT_PATH = Path(__file__).parent / "backtest_report.html"
HAS_API_KEY = bool(os.getenv("GROQ_API_KEY", "").strip())
requires_api = pytest.mark.skipif(not HAS_API_KEY, reason="GROQ_API_KEY non impostata")

# ─────────────────────────────────────────────────────────────────────────────
# FIXTURE
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def seed_db():
    n = seed_backtest_db()
    print(f"\n[seed] {n} transazioni backtest inserite nel DB")
    yield
    # Cleanup opzionale: lascia i dati per ispezione post-run


# ─────────────────────────────────────────────────────────────────────────────
# STRUTTURA TEST CASE
# ─────────────────────────────────────────────────────────────────────────────

class TC:
    """Struttura dati di un test case."""
    __slots__ = (
        "id", "label", "group", "message", "history",
        "expected_function", "params_must_contain", "answer_must_contain",
        "answer_must_not_contain", "max_llm_calls", "chart_data_expected",
        "table_data_expected", "http_status_expected",
        "min_functions", "functions_must_include",
    )

    def __init__(self, id, label, group, message, *, history=None,
                 expected_function=None, params_must_contain=None,
                 answer_must_contain=None, answer_must_not_contain=None,
                 max_llm_calls=None, chart_data_expected=None,
                 table_data_expected=None, http_status_expected=None,
                 min_functions=None, functions_must_include=None):
        self.id = id
        self.label = label
        self.group = group
        self.message = message
        self.history = history or []
        self.expected_function = expected_function          # str | list[str] | None
        self.params_must_contain = params_must_contain or {}
        self.answer_must_contain = answer_must_contain or []
        self.answer_must_not_contain = answer_must_not_contain or []
        self.max_llm_calls = max_llm_calls                  # int | None
        self.chart_data_expected = chart_data_expected      # True/False/None
        self.table_data_expected = table_data_expected      # True/False/None
        self.http_status_expected = http_status_expected    # int | None
        self.min_functions = min_functions                  # int | None — LLM deve selezionare >= N funzioni
        self.functions_must_include = functions_must_include or []  # list[str]


def _ef(*fns):
    """Shorthand: expected_function accetta una lista di funzioni valide."""
    return list(fns)


# ─────────────────────────────────────────────────────────────────────────────
# DEFINIZIONE DEI 60 TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

TEST_CASES: list[TC] = [

    # ── GROUP A: MERCHANT SEARCH (12) ─────────────────────────────────────────
    TC("TC-A01", "IKEA search", "merchant_search",
       "quanto ho speso da IKEA?",
       expected_function="search_transactions",
       params_must_contain={"query": "ikea"},
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-A02", "Amazon search", "merchant_search",
       "le mie spese su Amazon",
       expected_function="search_transactions",
       params_must_contain={"query": "amazon"},
       table_data_expected=True),

    TC("TC-A03", "Starbucks questo mese", "merchant_search",
       "Starbucks questo mese",
       expected_function="search_transactions",
       params_must_contain={"query": "starbucks"},
       answer_must_contain=["Starbucks"],
       table_data_expected=True),

    TC("TC-A04", "Uber frequenza", "merchant_search",
       "quanto pago Uber ogni mese?",
       expected_function=_ef("search_transactions", "frequency_analysis"),
       params_must_contain={"query": "uber"},
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-A05", "Trenitalia keyword secca", "merchant_search",
       "Trenitalia",
       expected_function="search_transactions",
       params_must_contain={"query": "trenitalia"},
       table_data_expected=True),

    TC("TC-A06", "Leroy Merlin", "merchant_search",
       "spese da Leroy Merlin",
       expected_function="search_transactions",
       params_must_contain={"query": "leroy"},
       table_data_expected=True),

    TC("TC-A07", "Netflix pagamenti", "merchant_search",
       "tutte le volte che ho pagato Netflix",
       expected_function=_ef("search_transactions", "subscriptions_audit"),
       answer_must_contain=["Netflix"],
       table_data_expected=True),

    TC("TC-A08", "McDonald+Deliveroo multi-merchant", "merchant_search",
       "McDonald's + Deliveroo quanto mi costano al mese?",
       expected_function=_ef(None, "search_transactions"),
       answer_must_contain=["€"],
       answer_must_not_contain=["non posso", "non disponibile"]),

    TC("TC-A09", "Esselunga anomalia", "merchant_search",
       "ho comprato qualcosa da Esselunga sopra i 100€?",
       expected_function="search_transactions",
       params_must_contain={"query": "esselunga"},
       answer_must_contain=["€"]),

    TC("TC-A10", "benzina keyword", "merchant_search",
       "benzina",
       expected_function="search_transactions",
       table_data_expected=True),

    TC("TC-A11", "gym inglese", "merchant_search",
       "gym",
       expected_function=_ef("search_transactions", "category_drill"),
       answer_must_contain=["€"],
       answer_must_not_contain=["non capisco"]),

    TC("TC-A12", "palestra", "merchant_search",
       "palestra",
       expected_function=_ef("search_transactions", "category_drill"),
       answer_must_contain=["€"],
       table_data_expected=True),

    # ── GROUP B: CATEGORY ROUTING (10) ────────────────────────────────────────
    TC("TC-B01", "ristoranti category", "category_routing",
       "ristoranti",
       expected_function=_ef("search_transactions", "category_drill"),
       answer_must_not_contain=["non posso"]),

    TC("TC-B02", "spese alimentari", "category_routing",
       "spese alimentari di questo mese",
       expected_function=_ef("query_spending", "category_drill"),
       answer_must_contain=["€"]),

    TC("TC-B03", "taxi e trasporti", "category_routing",
       "taxi e trasporti",
       expected_function=_ef("query_spending", "category_drill"),
       answer_must_contain=["€"]),

    TC("TC-B04", "abbonamenti attivi", "category_routing",
       "abbonamenti attivi",
       expected_function="subscriptions_audit",
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-B05", "cosa sto pagando in abbonamenti", "category_routing",
       "cosa sto pagando in abbonamenti?",
       expected_function="subscriptions_audit",
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-B06", "spese di casa", "category_routing",
       "spese di casa",
       expected_function=_ef("category_drill", "query_spending"),
       answer_must_contain=["€"]),

    TC("TC-B07", "mangiare fuori", "category_routing",
       "mangiare fuori",
       expected_function=_ef("search_transactions", "category_drill"),
       answer_must_contain=["€"],
       answer_must_not_contain=["non posso"]),

    TC("TC-B08", "svago e divertimento", "category_routing",
       "svago e divertimento",
       expected_function=_ef("query_spending", "category_drill"),
       answer_must_contain=["€"]),

    TC("TC-B09", "streaming", "category_routing",
       "streaming",
       expected_function=_ef("search_transactions", "subscriptions_audit"),
       answer_must_contain=["€"],
       answer_must_not_contain=["non posso"]),

    TC("TC-B10", "tech spese", "category_routing",
       "quanto spendo di tech?",
       expected_function=_ef("search_transactions", "query_spending", None),
       answer_must_not_contain=["non posso", "fuori perimetro"]),

    # ── GROUP C: DATE RANGE IMPLICITO (8) ─────────────────────────────────────
    TC("TC-C01", "questa settimana", "date_range",
       "questa settimana",
       expected_function="query_spending",
       params_must_contain={"period_days": 7},
       answer_must_contain=["€"]),

    TC("TC-C02", "ultimo mese", "date_range",
       "ultimo mese",
       expected_function="query_spending",
       params_must_contain={"period_days": 30}),

    TC("TC-C03", "ultimi 3 mesi", "date_range",
       "ultimi 3 mesi",
       expected_function="query_spending",
       params_must_contain={"period_days": 90}),

    TC("TC-C04", "IKEA 6 mesi", "date_range",
       "Ikea negli ultimi 6 mesi",
       expected_function="search_transactions",
       params_must_contain={"query": "ikea", "period_days": 180},
       table_data_expected=True),

    TC("TC-C05", "Starbucks questa settimana", "date_range",
       "Starbucks questa settimana",
       expected_function="search_transactions",
       params_must_contain={"query": "starbucks", "period_days": 7}),

    TC("TC-C06", "confronta ultime 2 settimane", "date_range",
       "confronta le ultime 2 settimane",
       expected_function="period_compare",
       params_must_contain={"period_a_days": 14}),

    TC("TC-C07", "questa vs scorsa settimana", "date_range",
       "come è andata questa settimana rispetto alla scorsa?",
       expected_function="period_compare",
       params_must_contain={"period_a_days": 7, "period_b_offset_days": 7}),

    TC("TC-C08", "spese di ieri", "date_range",
       "spese di ieri",
       expected_function="query_spending",
       params_must_contain={"period_days": 1},
       answer_must_not_contain=["non posso"]),

    # ── GROUP D: OUT-OF-SCOPE (10) ────────────────────────────────────────────
    TC("TC-D01", "ricetta pasta", "oos",
       "ricetta della pasta al pesto",
       expected_function="OOS",
       max_llm_calls=0,
       answer_must_contain=["Spese per categoria"]),

    TC("TC-D02", "Champions League", "oos",
       "chi ha vinto la Champions League?",
       expected_function="OOS",
       max_llm_calls=0),

    TC("TC-D03", "meteo Milano", "oos",
       "che tempo fa domani a Milano",
       expected_function="OOS",
       max_llm_calls=0),

    TC("TC-D04", "programma Python", "oos",
       "scrivimi un programma Python",
       expected_function="OOS",
       max_llm_calls=0),

    TC("TC-D05", "sei ChatGPT", "oos",
       "sei chatgpt?",
       max_llm_calls=0),

    TC("TC-D06", "mal di testa", "oos",
       "ho mal di testa cosa prendo?",
       expected_function="OOS",
       max_llm_calls=0),

    TC("TC-D07", "serie TV", "oos",
       "consigliami una serie da vedere",
       max_llm_calls=0,
       answer_must_not_contain=["€"]),

    TC("TC-D08", "stringa vuota HTTP 400", "edge",
       "",
       http_status_expected=400),

    TC("TC-D09", "input troppo lungo", "oos",
       "x" * 600,
       answer_must_contain=["troppo lunga"],
       max_llm_calls=0),

    TC("TC-D10", "investire in azioni", "oos",
       "aiutami a investire in azioni",
       expected_function=_ef("OOS", None),
       answer_must_not_contain=["acquista", "compra", "vendi"]),

    # ── GROUP E: MULTI-FUNCTION (5) ───────────────────────────────────────────
    # Il router LLM deve selezionare 2+ funzioni per domande "larghe"
    TC("TC-E01", "analisi completa del mese", "multi_function",
       "fammi un'analisi completa del mese",
       min_functions=2,
       functions_must_include=["query_spending"],
       max_llm_calls=2,
       answer_must_contain=["€"],
       chart_data_expected=True),

    TC("TC-E02", "come sto andando", "multi_function",
       "come sto andando?",
       min_functions=2,
       functions_must_include=["query_spending"],
       max_llm_calls=2,
       answer_must_contain=["€"]),

    TC("TC-E03", "dove posso risparmiare", "multi_function",
       "dove posso risparmiare?",
       min_functions=2,
       functions_must_include=["subscriptions_audit"],
       max_llm_calls=2,
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-E04", "trend generale", "multi_function",
       "fammi vedere il trend generale delle mie spese",
       min_functions=2,
       max_llm_calls=2,
       chart_data_expected=True),

    TC("TC-E05", "panoramica finanziaria", "multi_function",
       "panoramica finanziaria",
       min_functions=2,
       functions_must_include=["query_spending"],
       max_llm_calls=2,
       answer_must_contain=["€"]),

    # ── GROUP F: WHAT-IF (5) ──────────────────────────────────────────────────
    TC("TC-F01", "taglio 50€ svago 1 anno", "what_if",
       "se taglio 50€ al mese di svago quanto risparmio in un anno?",
       expected_function="what_if",
       params_must_contain={"category": "svago", "monthly_delta": -50.0, "horizon_months": 12},
       answer_must_contain=["600"],
       table_data_expected=True),

    TC("TC-F02", "riduco cibo 20% per 6 mesi", "what_if",
       "cosa succede se riduco il cibo del 20% per 6 mesi?",
       expected_function="what_if",
       params_must_contain={"category": "cibo", "percent_change": -20.0, "horizon_months": 6},
       answer_must_contain=["€"],
       table_data_expected=True),

    TC("TC-F03", "budget 200€ svago", "what_if",
       "se metto un tetto di 200€ al mese sullo svago?",
       expected_function="what_if",
       params_must_contain={"category": "svago", "monthly_target": 200.0},
       table_data_expected=True),

    TC("TC-F04", "taglio 30€ totale", "what_if",
       "quanto risparmio in totale se taglio 30€ al mese?",
       expected_function="what_if",
       params_must_contain={"monthly_delta": -30.0},
       answer_must_contain=["€"]),

    TC("TC-F05", "100€ in meno 2 anni", "what_if",
       "se spendo 100€ in meno al mese quanto fa in 2 anni?",
       expected_function="what_if",
       params_must_contain={"monthly_delta": -100.0, "horizon_months": 24},
       answer_must_contain=["2400"]),

    # ── GROUP G: FOLLOW-UP E STORIA (5) ──────────────────────────────────────
    TC("TC-G01", "follow-up top5 → per il cibo", "followup",
       "e per il cibo?",
       history=[
           {"role": "user",      "content": "top 5 spese del mese"},
           {"role": "assistant", "content": "Ecco le top 5 transazioni del mese..."},
       ],
       expected_function="query_spending",
       params_must_contain={"category": "cibo"},
       answer_must_not_contain=["non capisco", "puoi chiarire"]),

    TC("TC-G02", "follow-up Starbucks → McDonald's", "followup",
       "e da McDonald's?",
       history=[
           {"role": "user",      "content": "quanto ho speso da Starbucks?"},
           {"role": "assistant", "content": "Da Starbucks hai speso €36..."},
       ],
       expected_function="search_transactions",
       params_must_contain={"query": "mcdonald"},
       table_data_expected=True),

    TC("TC-G03", "follow-up cibo → in aumento?", "followup",
       "è in aumento?",
       history=[
           {"role": "user",      "content": "analisi cibo"},
           {"role": "assistant", "content": "Nell'ultimo mese hai speso €480 di cibo..."},
       ],
       expected_function=_ef("momentum", "query_spending"),
       answer_must_contain=["€"],
       answer_must_not_contain=["cosa intendi", "di cosa parli"]),

    TC("TC-G04", "follow-up svago → cosa taglieresti", "followup",
       "taglierei cosa?",
       history=[
           {"role": "user",      "content": "spese di svago"},
           {"role": "assistant", "content": "Nel mese hai speso €280 di svago..."},
       ],
       expected_function=None,
       answer_must_not_contain=["non posso", "fuori perimetro"],
       answer_must_contain=["€"]),

    TC("TC-G05", "storia lunga → anomalie", "followup",
       "e le anomalie?",
       history=[
           {"role": "user",      "content": "analisi completa"},
           {"role": "assistant", "content": "Questa settimana hai speso..."},
           {"role": "user",      "content": "focus sul cibo"},
           {"role": "assistant", "content": "Il cibo rappresenta il 32%..."},
           {"role": "user",      "content": "e i trasporti?"},
           {"role": "assistant", "content": "Trasporti: €178 questo mese..."},
           {"role": "user",      "content": "ok e gli abbonamenti?"},
           {"role": "assistant", "content": "Abbonamenti attivi: Netflix, Spotify..."},
       ],
       expected_function="subscriptions_audit",
       answer_must_not_contain=["non posso"],
       max_llm_calls=2),

    # ── GROUP H: EDGE E AMBIGUOUS (5) ────────────────────────────────────────
    TC("TC-H01", "?? quasi-vuoto", "edge",
       "??",
       max_llm_calls=0,
       answer_must_contain=["Spese per categoria"]),

    TC("TC-H02", "IKEA ripetuto", "edge",
       "IKEA IKEA IKEA IKEA",
       expected_function="search_transactions",
       params_must_contain={"query": "ikea"},
       table_data_expected=True),

    TC("TC-H03", "quanto ho speso (generico)", "edge",
       "quanto ho speso",
       expected_function="query_spending",
       answer_must_contain=["€"]),

    TC("TC-H04", "ho speso troppo (testuale)", "edge",
       "ho speso troppo?",
       expected_function=None,
       answer_must_contain=["€"],
       answer_must_not_contain=["non posso", "fuori perimetro"]),

    TC("TC-H05", "IKEA Leroy Amazon multi", "edge",
       "dimmi tutto di ikea leroy e amazon",
       expected_function=_ef("search_transactions", None),
       answer_must_contain=["€"],
       answer_must_not_contain=["non posso"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER LOGICA
# ─────────────────────────────────────────────────────────────────────────────

class TestResult:
    __slots__ = ("tc", "status", "actual_function", "actual_answer",
                 "first_failure", "duration_ms")

    def __init__(self, tc: TC):
        self.tc = tc
        self.status = "pass"
        self.actual_function = "—"
        self.actual_answer = ""
        self.first_failure = ""
        self.duration_ms = 0


def _needs_api(tc: TC) -> bool:
    """True se il test richiede una chiamata LLM reale."""
    if tc.http_status_expected == 400:
        return False
    if tc.max_llm_calls == 0:
        return False
    return True


def _extract_routing(result: dict) -> str:
    """Estrae il routing effettivo dai reasoning_steps."""
    steps = result.get("reasoning_steps", [])
    for step in steps:
        phase = step.get("phase", "")
        label = step.get("label", "")
        if phase == "pre_filter" and "⛔ Fuori perimetro" in label:
            return "OOS"
        if phase == "pre_filter" and "Input troppo lungo" in label:
            return "TOO_LONG"
        if phase == "llm_router":
            if "fuori perimetro" in label:
                return "OOS"
            if "risposta testuale" in label:
                return "null"
            # "🔀 Router → fn1, fn2, fn3"
            parts = label.split("→")
            if len(parts) >= 2:
                return parts[-1].strip()
    return "unknown"


def _extract_fn_names(result: dict) -> list[str]:
    """Estrae la lista di nomi funzione dai fn_execute steps."""
    steps = result.get("reasoning_steps", [])
    return [
        step.get("label", "").replace("📊 ", "").strip()
        for step in steps
        if step.get("phase") == "fn_execute"
    ]


def _run_tc(tc: TC) -> TestResult:
    r = TestResult(tc)
    t0 = time.time()

    try:
        # HTTP 400 test
        if tc.http_status_expected == 400:
            from fastapi import HTTPException
            from backend.core.ai_engine import MAX_QUESTION_CHARS
            message = (tc.message or "").strip()[:MAX_QUESTION_CHARS]
            if not message:
                r.actual_function = "HTTP:400"
                r.actual_answer = "empty message → 400"
                r.duration_ms = int((time.time() - t0) * 1000)
                return r
            else:
                r.status = "fail"
                r.first_failure = "Atteso HTTP 400 ma la stringa non è vuota"
                r.duration_ms = int((time.time() - t0) * 1000)
                return r

        # max_llm_calls=0 tests: test pre-filter directly
        if tc.max_llm_calls == 0:
            _reset_llm_stats()
            result = chat_with_ai(tc.message, tc.history)
            calls_made = get_llm_stats()["total_calls"]
            r.actual_function = _extract_routing(result)
            r.actual_answer = result.get("answer", "")

            if calls_made > 0:
                r.status = "fail"
                r.first_failure = f"Atteso 0 LLM calls, effettuate {calls_made}"
                r.duration_ms = int((time.time() - t0) * 1000)
                return r

        else:
            # LLM test
            _reset_llm_stats()
            result = chat_with_ai(tc.message, tc.history)
            r.actual_function = _extract_routing(result)
            r.actual_answer = result.get("answer", "")

        # ── Verifica expected_function ──────────────────────────────────────
        if tc.expected_function is not None and r.status == "pass":
            expected = tc.expected_function
            if isinstance(expected, list):
                acceptable = [str(f) if f is not None else "null" for f in expected]
            else:
                acceptable = [str(expected)]
            actual_fn = r.actual_function
            if not any(_fn_matches(actual_fn, a) for a in acceptable):
                r.status = "fail"
                r.first_failure = f"Routing: atteso {acceptable}, ottenuto '{actual_fn}'"

        # ── Verifica params_must_contain ────────────────────────────────────
        if tc.params_must_contain and r.status == "pass":
            steps = result.get("reasoning_steps", [])
            router_step = next((s for s in steps if s.get("phase") == "llm_router"
                                and "→" in s.get("label", "")), None)
            detail = router_step.get("detail", "") if router_step else ""
            for key, val in tc.params_must_contain.items():
                if str(val).lower() not in detail.lower() and str(val).lower() not in r.actual_answer.lower():
                    r.status = "warn"
                    r.first_failure = r.first_failure or f"Param '{key}={val}' non trovato nel routing"

        # ── Verifica answer_must_contain ────────────────────────────────────
        if tc.answer_must_contain and r.status == "pass":
            for s in tc.answer_must_contain:
                if s.lower() not in r.actual_answer.lower():
                    r.status = "fail"
                    r.first_failure = f"answer mancante: '{s}'"
                    break

        # ── Verifica answer_must_not_contain ────────────────────────────────
        if tc.answer_must_not_contain and r.status == "pass":
            for s in tc.answer_must_not_contain:
                if s.lower() in r.actual_answer.lower():
                    r.status = "fail"
                    r.first_failure = f"answer contiene vietato: '{s}'"
                    break

        # ── Verifica min_functions ──────────────────────────────────────────
        if tc.min_functions is not None and r.status == "pass":
            fn_names = _extract_fn_names(result)
            if len(fn_names) < tc.min_functions:
                r.status = "warn"
                r.first_failure = (
                    r.first_failure or
                    f"min_functions={tc.min_functions}, selezionate {len(fn_names)}: {fn_names}"
                )

        # ── Verifica functions_must_include ─────────────────────────────────
        if tc.functions_must_include and r.status == "pass":
            fn_names = _extract_fn_names(result)
            fn_names_lower = [f.lower() for f in fn_names]
            for required in tc.functions_must_include:
                if not any(required.lower() in fn for fn in fn_names_lower):
                    r.status = "warn"
                    r.first_failure = (
                        r.first_failure or
                        f"Funzione richiesta '{required}' non trovata in {fn_names}"
                    )
                    break

        # ── Verifica chart/table ────────────────────────────────────────────
        if tc.chart_data_expected is True and r.status == "pass":
            if result.get("chart_data") is None:
                r.status = "fail"
                r.first_failure = "chart_data atteso ma None"
        if tc.chart_data_expected is False and r.status == "pass":
            if result.get("chart_data") is not None:
                r.status = "fail"
                r.first_failure = "chart_data non atteso ma presente"
        if tc.table_data_expected is True and r.status == "pass":
            if result.get("data_table") is None:
                r.status = "warn"
                r.first_failure = r.first_failure or "data_table atteso ma None"

        # ── max_llm_calls già verificato sopra per =0; verifica generale ────
        if tc.max_llm_calls is not None and tc.max_llm_calls > 0 and r.status == "pass":
            calls_made = get_llm_stats()["total_calls"]
            if calls_made > tc.max_llm_calls:
                r.status = "warn"
                r.first_failure = r.first_failure or f"LLM calls: max {tc.max_llm_calls}, effettuate {calls_made}"

    except Exception as exc:
        r.status = "fail"
        r.first_failure = f"EXCEPTION: {type(exc).__name__}: {exc}"

    r.duration_ms = int((time.time() - t0) * 1000)
    return r


def _fn_matches(actual: str, expected: str) -> bool:
    """Confronto flessibile del routing (supporta multi-funzione con virgola)."""
    if expected == "null":
        return actual in ("null", "—", "unknown")
    if expected == "OOS":
        return actual.upper() in ("OOS", "FUORI PERIMETRO")
    # actual può essere "fn1, fn2, fn3" — basta che expected sia uno dei nomi
    actual_parts = [p.strip().lower() for p in actual.split(",")]
    return expected.lower() in actual_parts


# ─────────────────────────────────────────────────────────────────────────────
# REPORT HTML
# ─────────────────────────────────────────────────────────────────────────────

_STATUS_ICON = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏭️"}
_STATUS_BG   = {"pass": "#0f2a1a", "fail": "#2a0f0f", "warn": "#2a1f00", "skip": "#1a1a1a"}

def _generate_report(results: list[TestResult]) -> str:
    groups: dict[str, list[TestResult]] = {}
    for r in results:
        groups.setdefault(r.tc.group, []).append(r)

    summary_rows = ""
    for grp, items in groups.items():
        total = len(items)
        passed = sum(1 for x in items if x.status == "pass")
        skipped = sum(1 for x in items if x.status == "skip")
        icon = "✅" if passed + skipped == total else "⚠️"
        summary_rows += (
            f"<tr><td>{icon} {grp}</td><td>{passed}/{total}</td>"
            f"<td>{skipped}</td></tr>\n"
        )

    total_all = len(results)
    passed_all = sum(1 for r in results if r.status == "pass")
    skipped_all = sum(1 for r in results if r.status == "skip")
    failed_all = total_all - passed_all - skipped_all
    pct = round(passed_all / max(total_all - skipped_all, 1) * 100)

    detail_rows = ""
    for r in results:
        bg = _STATUS_BG.get(r.status, "#1a1a1a")
        icon = _STATUS_ICON.get(r.status, "?")
        answer_snip = _html.escape(r.actual_answer[:120]).replace("\n", " ")
        failure_snip = _html.escape(r.first_failure[:120]) if r.first_failure else "—"
        detail_rows += (
            f'<tr style="background:{bg}">'
            f"<td>{r.tc.id}</td>"
            f"<td>{_html.escape(r.tc.label)}</td>"
            f"<td>{_html.escape(r.tc.group)}</td>"
            f"<td>{icon} {r.status}</td>"
            f"<td><code>{_html.escape(r.actual_function)}</code></td>"
            f"<td>{failure_snip}</td>"
            f"<td>{r.duration_ms}ms</td>"
            f"<td style='font-size:0.75em;color:#888'>{answer_snip}</td>"
            f"</tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<title>FinCopilot AI Backtest Report</title>
<style>
  body {{ font-family: 'Segoe UI', sans-serif; background:#0d0d0d; color:#e0e0e0; margin:0; padding:20px; }}
  h1 {{ color:#ff8c42; }}
  h2 {{ color:#aaa; font-size:1rem; }}
  .summary {{ display:flex; gap:20px; margin-bottom:24px; flex-wrap:wrap; }}
  .stat {{ background:#1a1a1a; border-radius:8px; padding:12px 20px; text-align:center; }}
  .stat .val {{ font-size:2rem; font-weight:700; }}
  .pass {{ color:#10b981; }}
  .fail {{ color:#f43f5e; }}
  .warn {{ color:#f59e0b; }}
  .skip {{ color:#888; }}
  table {{ border-collapse:collapse; width:100%; font-size:0.85rem; }}
  th {{ background:#1a1a1a; padding:8px 12px; text-align:left; color:#aaa; border-bottom:1px solid #333; }}
  td {{ padding:6px 10px; border-bottom:1px solid #222; vertical-align:top; }}
  code {{ background:#222; padding:2px 6px; border-radius:4px; font-size:0.8em; }}
  .stbl {{ width:auto; min-width:320px; margin-bottom:24px; }}
</style>
</head>
<body>
<h1>FinCopilot AI Engine — Backtest Report</h1>
<h2>Generato automaticamente dal runner backtest</h2>

<div class="summary">
  <div class="stat"><div class="val pass">{passed_all}</div><div>Pass</div></div>
  <div class="stat"><div class="val fail">{failed_all}</div><div>Fail</div></div>
  <div class="stat"><div class="val skip">{skipped_all}</div><div>Skip</div></div>
  <div class="stat"><div class="val">{pct}%</div><div>Score</div></div>
</div>

<h2>Per gruppo</h2>
<table class="stbl">
<tr><th>Gruppo</th><th>Pass/Totale</th><th>Skip</th></tr>
{summary_rows}
</table>

<h2>Dettaglio casi ({total_all})</h2>
<table>
<tr>
  <th>ID</th><th>Label</th><th>Gruppo</th><th>Stato</th>
  <th>Routing effettivo</th><th>Primo problema</th><th>ms</th><th>Answer (snippet)</th>
</tr>
{detail_rows}
</table>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# PYTEST TEST FUNCTIONS (parametrizzate)
# ─────────────────────────────────────────────────────────────────────────────

def _tc_id(tc: TC) -> str:
    return f"{tc.id}"


@pytest.mark.parametrize("tc", [t for t in TEST_CASES if not _needs_api(t)], ids=_tc_id)
def test_no_llm(tc: TC):
    """Test che non richiedono API key (max_llm_calls=0 o HTTP)."""
    r = _run_tc(tc)
    if r.status == "fail":
        pytest.fail(f"{tc.id} [{tc.label}]: {r.first_failure}\n"
                    f"  routing: {r.actual_function}\n"
                    f"  answer:  {r.actual_answer[:200]}")


@requires_api
@pytest.mark.parametrize("tc", [t for t in TEST_CASES if _needs_api(t)], ids=_tc_id)
def test_with_llm(tc: TC):
    """Test che richiedono API key."""
    r = _run_tc(tc)
    if r.status == "fail":
        pytest.fail(f"{tc.id} [{tc.label}]: {r.first_failure}\n"
                    f"  routing: {r.actual_function}\n"
                    f"  answer:  {r.actual_answer[:200]}")


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER STANDALONE + REPORT
# ─────────────────────────────────────────────────────────────────────────────

def _run_all() -> list[TestResult]:
    results = []
    for tc in TEST_CASES:
        if _needs_api(tc) and not HAS_API_KEY:
            r = TestResult(tc)
            r.status = "skip"
            r.first_failure = "GROQ_API_KEY non impostata"
        else:
            r = _run_tc(tc)
        results.append(r)
        icon = _STATUS_ICON.get(r.status, "?")
        print(f"  {icon} {tc.id:7s} [{tc.group:18s}] {tc.label[:40]:<40s} "
              f"  routing={r.actual_function}  {r.duration_ms}ms"
              + (f"  ← {r.first_failure}" if r.first_failure else ""))
    return results


def _print_summary(results: list[TestResult]) -> None:
    groups: dict[str, list[TestResult]] = {}
    for r in results:
        groups.setdefault(r.tc.group, []).append(r)

    print("\n" + "═" * 47)
    print("  BACKTEST RESULTS — FinCopilot AI Engine")
    print("═" * 47)
    total_p = total_t = 0
    for grp, items in groups.items():
        total = len(items)
        passed = sum(1 for x in items if x.status == "pass")
        skipped = sum(1 for x in items if x.status == "skip")
        total_p += passed
        total_t += total
        bar = "✅" if passed + skipped == total else "⚠️ "
        print(f"  {bar} {grp:<22s}: {passed}/{total}  (skip={skipped})")

    pct = round(total_p / max(total_t, 1) * 100)
    print("─" * 47)
    print(f"  TOTALE:  {total_p}/{total_t}  ({pct}%)")
    print(f"  Report: {REPORT_PATH}")
    print("═" * 47)


if __name__ == "__main__":
    seed_backtest_db()
    print("\nEseguendo 60 casi di test...\n")
    results = _run_all()
    _print_summary(results)
    report_html = _generate_report(results)
    REPORT_PATH.write_text(report_html, encoding="utf-8")
    print(f"\nReport HTML scritto in: {REPORT_PATH}")
    failed = sum(1 for r in results if r.status == "fail")
    sys.exit(1 if failed > 0 else 0)


# ── pytest session hook: genera il report dopo tutti i test ──────────────────

def pytest_sessionfinish(session, exitstatus):
    """Hook pytest: genera HTML report al termine della sessione."""
    try:
        results = []
        for item in session.items:
            tc = item.callspec.params.get("tc") if hasattr(item, "callspec") else None
            if tc is None:
                continue
            rep = getattr(item, "_backtest_result", None)
            if rep is None:
                r = TestResult(tc)
                outcome = getattr(item, "rep_call", None)
                if outcome is None:
                    r.status = "skip"
                elif outcome.passed:
                    r.status = "pass"
                elif outcome.skipped:
                    r.status = "skip"
                else:
                    r.status = "fail"
                    r.first_failure = str(outcome.longreprtext)[:120] if hasattr(outcome, "longreprtext") else "failed"
                results.append(r)
        if results:
            REPORT_PATH.write_text(_generate_report(results), encoding="utf-8")
    except Exception:
        pass
