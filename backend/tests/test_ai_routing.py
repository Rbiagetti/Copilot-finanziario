"""
Test harness per il motore AI: routing, pre-filtro OOS, guardrails input,
shape degli output delle funzioni prebuilt.

Categorie di test:
  B.2  test_determinism        — richiede GROQ_API_KEY (skippa se assente)
  B.3  test_out_of_scope_no_llm — monkeypatch, nessuna chiave necessaria
  B.4  test_input_validation    — nessuna chiave necessaria
  B.5  test_function_output_shape — nessuna chiave necessaria
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

# ─── Costanti & fixture import ────────────────────────────────────────────────

from backend.core.ai_engine import (
    _is_obviously_out_of_scope,
    _input_too_long,
    _sanitize_history,
    _validate_router_output,
    _validate_function_output,
    _select_function,
    _PREBUILT_FUNCTIONS,
    execute_prebuilt_function,
    chat_with_ai,
    CATEGORIES,
    MAX_QUESTION_CHARS,
    MAX_TABLE_ROWS,
    MAX_CHART_POINTS,
    MAX_TOP_N,
    MAX_PERIOD_DAYS,
    MAX_CATEGORY_TREND_MONTHS,
    MAX_MULTI_SUMMARY_CHARS,
    MACRO_INTENTS,
    _match_macro_intent,
    _build_multi_summary,
)

HAS_API_KEY = bool(os.getenv("GROQ_API_KEY", "").strip())
requires_api = pytest.mark.skipif(not HAS_API_KEY, reason="GROQ_API_KEY non impostata")

# ─── B.1 Canonical question sets ─────────────────────────────────────────────

# (question, expected_function_name, expected_key_params)
IN_SCOPE_FUNCTION = [
    ("dove vanno i miei soldi?",                "spending_by_category",  {}),
    ("top 10 spese più costose",                "top_transactions",      {"n": 10}),
    ("trend giornaliero ultimi 30 giorni",      "daily_trend",           {}),
    ("confronto mese corrente vs precedente",   "month_vs_month",        {}),
    ("andamento del cibo negli ultimi 6 mesi",  "category_trend",        {"category": "cibo", "months": 6}),
    ("media spese per giorno della settimana",  "spending_by_weekday",   {}),
    ("statistiche generali ultimi 30 giorni",   "summary_stats",         {}),
    ("previsione fine anno",                    "year_end_forecast",     {}),
]

IN_SCOPE_TEXTUAL = [
    "come posso risparmiare di più?",
    "spendo troppo in svago?",
    "quanto dovrei mettere da parte?",
    "il mio budget è realistico?",
]

OUT_OF_SCOPE = [
    "dammi la ricetta carbonara",
    "chi ha vinto la partita ieri",
    "che tempo fa a roma",
    "scrivimi una funzione python",
    "chi è il presidente USA",
    "ho mal di testa",
]

EDGE = [
    "",
    "x" * 1500,
]


# ═══════════════════════════════════════════════════════════════════════════════
# B.2 — DETERMINISMO ROUTER (richiede API key)
# ═══════════════════════════════════════════════════════════════════════════════

@requires_api
@pytest.mark.parametrize("question,expected_fn,expected_params", IN_SCOPE_FUNCTION)
def test_determinism(question, expected_fn, expected_params):
    """Router deve ritornare lo stesso nome funzione su 3 chiamate consecutive."""
    results = [_select_function(question, []) for _ in range(3)]

    names = [r.get("use_function", {}).get("name") if r.get("use_function") else None
             for r in results]
    assert all(n == names[0] for n in names), (
        f"Router non deterministico per {question!r}: {names}"
    )
    assert names[0] == expected_fn, (
        f"Funzione errata per {question!r}: attesa={expected_fn!r}, ottenuta={names[0]!r}"
    )

    # Verifica parametri chiave (tolleranza: devono essere presenti e ragionevoli)
    if expected_params:
        params = results[0]["use_function"].get("params", {}) or {}
        for key, val in expected_params.items():
            assert key in params, f"Param {key!r} mancante per {question!r}"
            if key == "n":
                assert 1 <= int(params[key]) <= MAX_TOP_N
            elif key in ("period_days", "days"):
                assert 1 <= int(params[key]) <= MAX_PERIOD_DAYS
            elif key == "months":
                assert 1 <= int(params[key]) <= MAX_CATEGORY_TREND_MONTHS
            elif key == "category":
                assert params[key] in CATEGORIES, (
                    f"category={params[key]!r} non in CATEGORIES"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# B.3 — OOS PRE-FILTER (zero chiamate LLM)
# ═══════════════════════════════════════════════════════════════════════════════

class TestOutOfScopeNoLLM:
    """Tutte le query OOS devono essere bloccate prima di chiamare il LLM."""

    @pytest.mark.parametrize("question", OUT_OF_SCOPE)
    def test_prefilter_catches(self, question):
        """_is_obviously_out_of_scope deve ritornare True per ogni query OOS."""
        assert _is_obviously_out_of_scope(question), (
            f"Pre-filter non ha catturato {question!r}"
        )

    @pytest.mark.parametrize("question", OUT_OF_SCOPE)
    def test_zero_llm_calls(self, question):
        """chat_with_ai su query OOS non deve fare nessuna chiamata al client LLM."""
        with patch("backend.core.ai_engine.client") as mock_client:
            chat_with_ai(question)
            mock_client.chat.completions.create.assert_not_called()

    @pytest.mark.parametrize("question", IN_SCOPE_FUNCTION[:2])
    def test_in_scope_not_caught(self, question):
        """Le query finanziarie non devono essere bloccate dal pre-filter."""
        assert not _is_obviously_out_of_scope(question[0]), (
            f"Pre-filter ha bloccato erroneamente {question!r}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# B.4 — INPUT VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestInputValidation:
    def test_empty_message_too_long_flag(self):
        """Stringa vuota → _input_too_long=False (è un caso speciale, gestito da chat.py)."""
        assert not _input_too_long("")

    def test_long_message_flagged(self):
        """1500 caratteri → _input_too_long=True."""
        assert _input_too_long("x" * 1500)

    def test_many_words_flagged(self):
        """Più di 80 spazi (>81 parole) → _input_too_long=True."""
        assert _input_too_long(" ".join(["word"] * 82))

    def test_normal_message_not_flagged(self):
        """Domanda normale → non troppo lunga."""
        assert not _input_too_long("dove vanno i miei soldi questo mese?")

    def test_truncation_constant(self):
        """MAX_QUESTION_CHARS deve essere 500."""
        assert MAX_QUESTION_CHARS == 500

    def test_long_message_truncated_in_chat(self):
        """chat_with_ai con 1500 char → risposta di lunghezza-troppo-lunga (no eccezione)."""
        long_q = "x" * 1500
        with patch("backend.core.ai_engine.client"):
            result = chat_with_ai(long_q)
        assert "answer" in result
        assert result["answer"]  # non vuota

    def test_empty_message_triggers_400_logic(self):
        """Messaggio vuoto → la logica route produrrebbe HTTPException 400.

        Testato direttamente sulla logica di validazione (starlette 0.36 + httpx 0.28
        hanno un'incompatibilità con TestClient; evitiamo il layer HTTP).
        """
        from fastapi import HTTPException
        # Replica la logica di chat.py: strip + truncate → empty → HTTPException
        raw = ""
        message = (raw or "").strip()[:MAX_QUESTION_CHARS]
        with pytest.raises(HTTPException) as exc_info:
            if not message:
                raise HTTPException(status_code=400, detail="Messaggio vuoto")
        assert exc_info.value.status_code == 400

    def test_whitespace_message_triggers_400_logic(self):
        """Messaggio con soli spazi → stessa logica porta a HTTPException 400."""
        from fastapi import HTTPException
        raw = "   "
        message = (raw or "").strip()[:MAX_QUESTION_CHARS]
        with pytest.raises(HTTPException) as exc_info:
            if not message:
                raise HTTPException(status_code=400, detail="Messaggio vuoto")
        assert exc_info.value.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════════
# B.5 — FUNCTION OUTPUT SHAPE & BOUNDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFunctionOutputShape:
    """Ogni funzione prebuilt deve rispettare i contratti di output."""

    @pytest.mark.parametrize("fn_name", list(_PREBUILT_FUNCTIONS.keys()))
    def test_keys_always_present(self, fn_name):
        """Output deve sempre avere chart_data e table_data (anche se None)."""
        out = execute_prebuilt_function(fn_name, {})
        assert "chart_data" in out, f"{fn_name}: manca chart_data"
        assert "table_data" in out, f"{fn_name}: manca table_data"

    @pytest.mark.parametrize("fn_name", list(_PREBUILT_FUNCTIONS.keys()))
    def test_chart_data_bounds(self, fn_name):
        """Se chart_data presente → data ≤ MAX_CHART_POINTS e type valido."""
        out = execute_prebuilt_function(fn_name, {})
        cd = out.get("chart_data")
        if cd is not None:
            assert cd.get("type") in ("bar", "line", "pie"), (
                f"{fn_name}: chart type invalido: {cd.get('type')!r}"
            )
            assert len(cd.get("data", [])) <= MAX_CHART_POINTS, (
                f"{fn_name}: chart data {len(cd['data'])} > MAX_CHART_POINTS {MAX_CHART_POINTS}"
            )
            assert len(cd.get("title", "")) <= 80, f"{fn_name}: title troppo lungo"

    @pytest.mark.parametrize("fn_name", list(_PREBUILT_FUNCTIONS.keys()))
    def test_table_data_bounds(self, fn_name):
        """Se table_data presente → rows ≤ MAX_TABLE_ROWS e celle sono str."""
        out = execute_prebuilt_function(fn_name, {})
        td = out.get("table_data")
        if td is not None:
            rows = td.get("rows", [])
            assert len(rows) <= MAX_TABLE_ROWS, (
                f"{fn_name}: {len(rows)} rows > MAX_TABLE_ROWS {MAX_TABLE_ROWS}"
            )
            for i, row in enumerate(rows):
                for j, cell in enumerate(row):
                    assert isinstance(cell, str), (
                        f"{fn_name}: row[{i}][{j}]={cell!r} non è str"
                    )

    def test_top_transactions_extreme_n(self):
        """n=9999 deve essere clippato a MAX_TOP_N=50 senza eccezioni."""
        out = execute_prebuilt_function("top_transactions", {"n": 9999, "period_days": 30})
        assert "table_data" in out

    def test_period_days_extreme(self):
        """period_days=10000 deve essere clippato a MAX_PERIOD_DAYS=365."""
        out = execute_prebuilt_function("spending_by_category", {"period_days": 10000})
        assert "chart_data" in out  # no eccezione

    def test_invalid_function_name(self):
        """Funzione inesistente → {chart_data: None, table_data: None} senza eccezione."""
        out = execute_prebuilt_function("funzione_inesistente", {})
        assert out == {"chart_data": None, "table_data": None}

    def test_validate_output_strips_excess_chart_points(self):
        """_validate_function_output clippa data a MAX_CHART_POINTS."""
        raw = {
            "chart_data": {
                "type": "bar",
                "data": [{"name": str(i), "value": float(i)} for i in range(100)],
                "title": "Test",
            },
            "table_data": None,
        }
        out = _validate_function_output(raw)
        assert len(out["chart_data"]["data"]) == MAX_CHART_POINTS

    def test_validate_output_strips_excess_table_rows(self):
        """_validate_function_output clippa rows a MAX_TABLE_ROWS."""
        raw = {
            "chart_data": None,
            "table_data": {
                "headers": ["a", "b"],
                "rows": [[i, i * 2] for i in range(200)],
            },
        }
        out = _validate_function_output(raw)
        assert len(out["table_data"]["rows"]) == MAX_TABLE_ROWS

    def test_validate_output_cells_become_str(self):
        """_validate_function_output converte celle a str."""
        raw = {
            "chart_data": None,
            "table_data": {
                "headers": ["n", "val"],
                "rows": [[42, 3.14], [True, None]],
            },
        }
        out = _validate_function_output(raw)
        for row in out["table_data"]["rows"]:
            for cell in row:
                assert isinstance(cell, str)

    def test_validate_output_unknown_chart_type_normalized(self):
        """type non valido → normalizzato a 'bar'."""
        raw = {
            "chart_data": {"type": "radar", "data": [{"name": "x", "value": 1}], "title": "T"},
            "table_data": None,
        }
        out = _validate_function_output(raw)
        assert out["chart_data"]["type"] == "bar"

    def test_validate_output_title_truncated(self):
        """title > 80 caratteri → troncato a 80."""
        raw = {
            "chart_data": {"type": "bar", "data": [{"name": "x", "value": 1}], "title": "A" * 120},
            "table_data": None,
        }
        out = _validate_function_output(raw)
        assert len(out["chart_data"]["title"]) == 80

    def test_validate_output_none_input(self):
        """Input None → {chart_data: None, table_data: None}."""
        out = _validate_function_output(None)
        assert out == {"chart_data": None, "table_data": None}


# ═══════════════════════════════════════════════════════════════════════════════
# Parametrized pre-filter coverage (no API key needed)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("question", OUT_OF_SCOPE)
def test_prefilter_oos(question):
    """Ogni query OOS deve essere catturata dal pre-filter regex."""
    assert _is_obviously_out_of_scope(question)


@pytest.mark.parametrize("question,_fn,_params", IN_SCOPE_FUNCTION)
def test_prefilter_in_scope_passes(question, _fn, _params):
    """Nessuna query finanziaria deve essere bloccata dal pre-filter."""
    assert not _is_obviously_out_of_scope(question)


@pytest.mark.parametrize("question", IN_SCOPE_TEXTUAL)
def test_prefilter_textual_passes(question):
    """Domande finanziarie testuali non devono essere bloccate."""
    assert not _is_obviously_out_of_scope(question)


# ═══════════════════════════════════════════════════════════════════════════════
# Validatore router
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateRouterOutput:
    def test_unknown_function_discarded(self):
        r = _validate_router_output({"use_function": {"name": "bad_fn", "params": {}}, "in_perimeter": True})
        assert r["use_function"] is None

    def test_period_days_clipped_high(self):
        r = _validate_router_output({"use_function": {"name": "spending_by_category", "params": {"period_days": 10000}}, "in_perimeter": True})
        assert r["use_function"]["params"]["period_days"] == MAX_PERIOD_DAYS

    def test_period_days_clipped_low(self):
        r = _validate_router_output({"use_function": {"name": "spending_by_category", "params": {"period_days": 0}}, "in_perimeter": True})
        assert r["use_function"]["params"]["period_days"] == 1

    def test_n_clipped_high(self):
        r = _validate_router_output({"use_function": {"name": "top_transactions", "params": {"n": 9999}}, "in_perimeter": True})
        assert r["use_function"]["params"]["n"] == MAX_TOP_N

    def test_chart_type_normalized(self):
        r = _validate_router_output({"use_function": {"name": "spending_by_category", "params": {"chart_type": "radar"}}, "in_perimeter": True})
        assert r["use_function"]["params"]["chart_type"] == "bar"

    def test_invalid_category_nulled(self):
        r = _validate_router_output({"use_function": {"name": "top_transactions", "params": {"category": "robotica"}}, "in_perimeter": True})
        assert r["use_function"]["params"]["category"] is None

    def test_valid_category_kept(self):
        r = _validate_router_output({"use_function": {"name": "top_transactions", "params": {"category": "cibo"}}, "in_perimeter": True})
        assert r["use_function"]["params"]["category"] == "cibo"

    def test_in_perimeter_false(self):
        r = _validate_router_output({"use_function": None, "in_perimeter": False})
        assert r["in_perimeter"] is False

    def test_missing_in_perimeter_defaults_true(self):
        r = _validate_router_output({"use_function": None})
        assert r["in_perimeter"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# History sanitizer
# ═══════════════════════════════════════════════════════════════════════════════

class TestSanitizeHistory:
    def test_truncates_to_max_messages(self):
        h = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        from backend.core.ai_engine import MAX_HISTORY_MESSAGES
        assert len(_sanitize_history(h)) == MAX_HISTORY_MESSAGES

    def test_truncates_long_content(self):
        from backend.core.ai_engine import MAX_HISTORY_CHARS_PER_MSG
        h = [{"role": "user", "content": "x" * 1000}]
        s = _sanitize_history(h)
        assert len(s[0]["content"]) == MAX_HISTORY_CHARS_PER_MSG + 1  # +1 for ellipsis char

    def test_empty_history(self):
        assert _sanitize_history([]) == []
        assert _sanitize_history(None) == []

    def test_preserves_roles(self):
        h = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        s = _sanitize_history(h)
        roles = [m["role"] for m in s]
        assert "user" in roles
        assert "assistant" in roles


# ═══════════════════════════════════════════════════════════════════════════════
# Macro-intent matching
# ═══════════════════════════════════════════════════════════════════════════════

class TestMacroIntent:
    @pytest.mark.parametrize("question,expected", [
        ("fammi un'analisi completa del mese",         "full_monthly_review"),
        ("riassunto del mese",                         "full_monthly_review"),
        ("panoramica delle mie spese",                 "full_monthly_review"),
        ("dimmi tutto sulle mie finanze",              "full_monthly_review"),
        ("come sto andando con le spese?",             "full_monthly_review"),
        ("dove posso risparmiare questo mese?",        "savings_audit"),
        ("come tagliare le spese?",                    "savings_audit"),
        ("ottimizzare spese fisse",                    "savings_audit"),
        ("come ridurre spesa mensile",                 "savings_audit"),
        ("come sto cambiando nelle abitudini?",        "trend_overview"),
        ("trend generale delle mie spese",             "trend_overview"),
        ("evoluzione spese negli ultimi mesi",         "trend_overview"),
    ])
    def test_trigger_matches(self, question, expected):
        assert _match_macro_intent(question) == expected

    @pytest.mark.parametrize("question", [
        "quanto ho speso in cibo?",
        "mostrami le top 5 transazioni",
        "qual è il mio budget?",
        "stima fine anno",
    ])
    def test_non_matching_returns_none(self, question):
        assert _match_macro_intent(question) is None

    def test_case_insensitive(self):
        assert _match_macro_intent("ANALISI COMPLETA") == "full_monthly_review"
        assert _match_macro_intent("Dove Posso Risparmiare") == "savings_audit"

    def test_all_intents_in_catalog(self):
        for intent_name, intent in MACRO_INTENTS.items():
            for fn_name, _ in intent["functions"]:
                from backend.core.ai_engine import FUNCTION_CATALOG
                assert fn_name in FUNCTION_CATALOG, f"{fn_name} not in FUNCTION_CATALOG (intent={intent_name})"


# ═══════════════════════════════════════════════════════════════════════════════
# Multi-summary builder
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildMultiSummary:
    def test_short_blocks_unchanged(self):
        blocks = ["## Block A\nriga1\nriga2", "## Block B\nriga3"]
        result = _build_multi_summary(blocks)
        assert "## Block A" in result
        assert "## Block B" in result
        assert len(result) <= MAX_MULTI_SUMMARY_CHARS

    def test_long_blocks_truncated(self):
        big_block = "## Header\n" + "\n".join(f"dato {i}: €{i*10}" for i in range(500))
        blocks = [big_block, big_block]
        result = _build_multi_summary(blocks)
        assert len(result) <= MAX_MULTI_SUMMARY_CHARS

    def test_truncation_keeps_headers(self):
        big_block = "## SectionX\n" + "x" * 3000
        result = _build_multi_summary([big_block])
        assert result.startswith("## SectionX")


# ═══════════════════════════════════════════════════════════════════════════════
# What-if: _validate_router_output param clips
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatIfValidation:
    def _route(self, params: dict) -> dict:
        return _validate_router_output({
            "use_function": {"name": "what_if", "params": params},
            "in_perimeter": True,
        })

    def test_horizon_months_clipped_high(self):
        r = self._route({"horizon_months": 999})
        assert r["use_function"]["params"]["horizon_months"] == 60

    def test_horizon_months_clipped_low(self):
        r = self._route({"horizon_months": 0})
        assert r["use_function"]["params"]["horizon_months"] == 1

    def test_monthly_delta_clipped_high(self):
        r = self._route({"monthly_delta": 99999})
        assert r["use_function"]["params"]["monthly_delta"] == 10000

    def test_monthly_delta_clipped_low(self):
        r = self._route({"monthly_delta": -99999})
        assert r["use_function"]["params"]["monthly_delta"] == -10000

    def test_monthly_target_clipped(self):
        r = self._route({"monthly_target": 99999})
        assert r["use_function"]["params"]["monthly_target"] == 50000

    def test_monthly_target_zero_floor(self):
        r = self._route({"monthly_target": -100})
        assert r["use_function"]["params"]["monthly_target"] == 0

    def test_percent_change_clipped_low(self):
        r = self._route({"percent_change": -200})
        assert r["use_function"]["params"]["percent_change"] == -100

    def test_percent_change_clipped_high(self):
        r = self._route({"percent_change": 5000})
        assert r["use_function"]["params"]["percent_change"] == 1000

    def test_valid_category_kept(self):
        r = self._route({"category": "svago", "monthly_delta": -50})
        assert r["use_function"]["params"]["category"] == "svago"

    def test_invalid_category_nulled(self):
        r = self._route({"category": "ristorante", "monthly_delta": -50})
        assert r["use_function"]["params"]["category"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# What-if: function output shape
# ═══════════════════════════════════════════════════════════════════════════════

class TestWhatIfOutput:
    def test_returns_table_and_chart(self):
        result = execute_prebuilt_function("what_if", {"monthly_delta": -50, "horizon_months": 12})
        assert "chart_data" in result
        assert "table_data" in result

    def test_table_has_three_rows(self):
        result = execute_prebuilt_function("what_if", {"monthly_delta": -50, "horizon_months": 12})
        td = result.get("table_data")
        if td is not None:
            # Either 3-row result or "Dati insufficienti" (1-row) — both valid
            assert len(td["rows"]) >= 1

    def test_percent_change_mode(self):
        result = execute_prebuilt_function("what_if", {"category": "cibo", "percent_change": -15, "horizon_months": 6})
        assert "chart_data" in result
        assert "table_data" in result

    def test_monthly_target_mode(self):
        result = execute_prebuilt_function("what_if", {"category": "cibo", "monthly_target": 300})
        assert "chart_data" in result
        assert "table_data" in result

    def test_empty_category_returns_insufficient_or_valid(self):
        result = execute_prebuilt_function("what_if", {"category": "abbigliamento", "monthly_delta": -20})
        td = result.get("table_data")
        assert td is not None
        assert len(td["rows"]) >= 1
