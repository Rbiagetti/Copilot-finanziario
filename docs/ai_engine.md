# FinCopilot — AI Engine Reference

> File: `backend/core/ai_engine.py`  
> Ultima revisione: sprint 3 (robustezza, bounds, 12 funzioni)

---

## 1. Architettura

```
Richiesta utente (POST /api/v1/chat/)
         │
         ▼
┌─────────────────────────────────────────────┐
│  chat.py — Input guardrails                 │
│  • Trunca a MAX_QUESTION_CHARS (500)        │
│  • 400 su messaggio vuoto                   │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  chat_with_ai()                             │
│                                             │
│  1. AI_DISABLE_LLM=1? → OUT_OF_SCOPE <1ms  │
│  2. _input_too_long?   → risposta 500ch     │
│  3. _is_obviously_out_of_scope? → OOS <5ms  │
│     (7 pattern regex precompilati)          │
└────────────────────┬────────────────────────┘
                     │ in perimetro
                     ▼
┌─────────────────────────────────────────────┐
│  _select_function()   [LLM call #1: router] │
│  • temperature=0.0, seed=42                 │
│  • max_tokens=150, json_mode                │
│  • _sanitize_history() — max 4 msg, 300ch   │
│  • _validate_router_output()                │
│    – nome in FUNCTION_CATALOG               │
│    – params clippati ai range               │
│    – category in CATEGORIES o None          │
└────────────────────┬────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │ use_function        │ null, in_perimeter=true
          ▼                     ▼
┌─────────────────┐   ┌─────────────────────────────────┐
│ execute_        │   │ build_compact_context()          │
│ prebuilt_fn()   │   │ _answer_in_perimeter()           │
│ + _validate_    │   │ [LLM call #1: answer]            │
│   fn_output()   │   │ temperature=0.1, seed=42         │
└────────┬────────┘   └─────────────────┬───────────────┘
         │ data                          │
         ▼                               │
┌─────────────────────────────────────────────┐
│  _interpret_results()  [LLM call #2]        │
│  • temperature=0.1, seed=42                 │
│  • max_tokens=400, json_mode                │
└────────────────────┬────────────────────────┘
                     │
                     ▼
              ChatResponse JSON
    { answer, chart_data, data_table,
      followup_questions (max 2) }
```

**Totale chiamate LLM per richiesta con funzione:** 2 (router + interpret)  
**Totale chiamate LLM per risposta testuale:** 1 (answer)  
**Totale chiamate LLM per OOS/pre-filtro:** 0

---

## 2. Funzioni disponibili (12)

| # | Nome | Parametri | Range | Trigger principali |
|---|------|-----------|-------|-------------------|
| 1 | `spending_by_category` | `period_days=30` | 1..365 | "dove vanno i soldi", "distribuzione spese", "per categoria" |
| 2 | `daily_trend` | `days=30` | 1..365 | "trend giornaliero", "grafico spese nel tempo", "giorno per giorno" |
| 3 | `top_transactions` | `n=10`, `category=null`, `period_days=30` | n: 1..50, days: 1..365 | "spese più alte", "transazioni più costose", "top N" |
| 4 | `month_vs_month` | — | — | "confronto mesi", "questo mese vs mese scorso", "variazione mensile" |
| 5 | `spending_by_weekday` | `period_days=90` | 1..365 | "weekend vs feriali", "giorno più costoso", "media per giorno" |
| 6 | `category_trend` | `category`, `months=6` | months: 1..24 | "andamento [cat] nel tempo", "storico [cat] mesi" |
| 7 | `summary_stats` | `period_days=30` | 1..365 | "statistiche generali", "totale e media", "quante transazioni" |
| 8 | `year_end_forecast` | — | — | "stima fine anno", "previsione annuale", "quanto spenderò a dicembre" |
| 9 | `anomalies` | — | — | "spese strane", "anomalie", "transazioni fuori dalla norma", "pagamenti insoliti" |
| 10 | `budget_status` | — | — | "come vado coi budget", "sto sforando", "stato budget", "budget superato" |
| 11 | `recurring_vs_variable` | `period_days=90` | 1..365 | "fissi vs variabili", "quanto è ricorrente", "spese fisse" |
| 12 | `subscriptions_audit` | — | — | "lista abbonamenti", "audit subscription", "abbonamenti zombie", "ho abbonamenti attivi" |

### Output di ogni funzione

Ogni funzione ritorna `{ "chart_data": {...} | None, "table_data": {...} | None }`.  
Prima di essere restituito, l'output passa sempre per `_validate_function_output()`.

| Funzione | chart_data | table_data |
|----------|-----------|-----------|
| spending_by_category | bar (categorie) | — |
| daily_trend | line (giorni) | — |
| top_transactions | — | tabella transazioni |
| month_vs_month | bar (categorie mese corrente) | confronto mese |
| spending_by_weekday | bar (giorni settimana) | — |
| category_trend | line (mesi) | — |
| summary_stats | — | metriche riassuntive |
| year_end_forecast | bar (speso + previsto) | proiezione numerica |
| anomalies | bar (top 10 z-score) | tabella anomalie |
| budget_status | bar (% utilizzo) | semaforo per categoria |
| recurring_vs_variable | bar (ricorrenti/mese) | mese × fissi × variabili |
| subscriptions_audit | — | abbonamenti + annualizzato |

---

## 3. Limiti hard (costanti modulo)

| Costante | Valore | Dove applicata |
|----------|--------|----------------|
| `MAX_QUESTION_CHARS` | 500 | Trunca input in `chat.py` |
| `MAX_HISTORY_MESSAGES` | 4 | `_sanitize_history()` |
| `MAX_HISTORY_CHARS_PER_MSG` | 300 | `_sanitize_history()` |
| `MAX_DATA_SUMMARY_ROWS` | 12 | `_format_data_for_interpretation()` |
| `MAX_FOLLOWUP_QUESTIONS` | 2 | `chat_with_ai()` output |
| `MAX_TABLE_ROWS` | 30 | `_validate_function_output()`, SQL LIMIT |
| `MAX_CHART_POINTS` | 24 | `_validate_function_output()`, SQL LIMIT |
| `MAX_PERIOD_DAYS` | 365 | Clip param `period_days`, `days` in ogni `_fn_*` |
| `MAX_TOP_N` | 50 | Clip param `n` in `_fn_top_transactions` |
| `MAX_CATEGORY_TREND_MONTHS` | 24 | Clip param `months` in `_fn_category_trend` |

---

## 4. Determinismo

I seguenti meccanismi garantiscono output stabile su chiamate consecutive:

1. **`temperature=0.0` sul router** — nessuna varianza nella scelta funzione
2. **`seed=42`** su tutte le chiamate LLM (router + interpret + answer)
3. **`response_format={"type":"json_object"}`** — forza output JSON valido; con fallback automatico se non supportato dall'endpoint (log once via `_llm_state["response_format_supported"]`)
4. **`_validate_router_output()`** — sanifica nomi funzione, clippa param, normalizza category; elimina derive da output LLM malformato
5. **`_validate_function_output()`** — normalizza type enum, tronca title, clippa data/rows, converte celle a str
6. **Pre-filtro regex** — 7 domini OOS intercettati in <5ms senza LLM, output deterministico per definizione
7. **`_parse_ai_response()` fast-path** — gestisce raw vuoto o senza `{` senza eccezione

---

## 5. Flag runtime (env vars)

| Flag | Default | Effetto |
|------|---------|---------|
| `AI_DEBUG_ROUTING=1` | `0` | Log DEBUG del router: raw output LLM + validated dict |
| `AI_DISABLE_LLM=1` | `0` | Salta **tutte** le chiamate LLM. Ritorna `_OUT_OF_SCOPE` in <1ms. Utile per debug frontend e per emergenza costi. |
| `AI_FORCE_TEMP_ZERO=1` | `0` | Forza `temperature=0.0` sulle fasi `interpret`, `answer`, `briefing`. Il router è già a 0 e non è influenzato. |

### Come usare in sviluppo

```bash
# Debug frontend senza consumare token
AI_DISABLE_LLM=1 uvicorn backend.main:app --reload

# Massima determinismo in staging
AI_FORCE_TEMP_ZERO=1 uvicorn backend.main:app

# Log routing per diagnosi
AI_DEBUG_ROUTING=1 uvicorn backend.main:app
```

### Come usare in produzione (emergenza costi)

```bash
# Stop immediato a tutte le spese LLM senza fermare il server
# Il frontend riceve una risposta "non disponibile" invece di errore
AI_DISABLE_LLM=1 systemctl restart fincopilot-backend
```

---

## 6. Costi stimati

Basato su statistiche reali da `GET /api/v1/chat/stats`.  
Modello: Groq `llama-3.3-70b-versatile` (novembre 2024: $0.59/M input token, $0.79/M output token).

### Token per richiesta (stima)

| Fase | Input token (stima) | Output token (stima) |
|------|---------------------|----------------------|
| Router | ~600 (system prompt + storia + domanda) | ~40 (JSON funzione) |
| Interpret | ~400 (prompt + data summary ≤12 righe) | ~120 (analisi + followup) |
| Answer (testuale) | ~350 (compact context + domanda) | ~100 |

**Totale per richiesta con funzione:** ~1.160 input + ~160 output token  
**Totale per risposta testuale:** ~950 input + ~100 output token

### Costi aggregati

| Richieste | Costo stimato (funzione) | Costo stimato (testuale) |
|-----------|--------------------------|--------------------------|
| 1 | ~$0.00082 | ~$0.00064 |
| 100 | ~$0.082 | ~$0.064 |
| 1.000 | ~$0.82 | ~$0.64 |
| 10.000 | ~$8.20 | ~$6.40 |

> **Nota:** Le query bloccate dal pre-filtro OOS (regex) o da `AI_DISABLE_LLM` hanno costo zero.  
> Il contatore `get_llm_stats()` traccia le chiamate reali per fase dall'avvio del processo.

### Come monitorare i costi in tempo reale

```bash
curl http://localhost:8000/api/v1/chat/stats
# {"total_calls": 42, "by_phase": {"router": 18, "interpret": 17, "answer": 7}, "json_mode_supported": true}
```
