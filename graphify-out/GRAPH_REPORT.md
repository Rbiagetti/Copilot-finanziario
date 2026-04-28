# Graph Report - copilota-finanziario  (2026-04-29)

## Corpus Check
- 46 files · ~44,121 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 403 nodes · 620 edges · 21 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 142 edges (avg confidence: 0.68)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]

## God Nodes (most connected - your core abstractions)
1. `_q()` - 24 edges
2. `_dates()` - 23 edges
3. `Transaction` - 20 edges
4. `chat_with_ai()` - 17 edges
5. `execute_prebuilt_function()` - 14 edges
6. `_validate_router_output()` - 14 edges
7. `TestWhatIfValidation` - 12 edges
8. `_run_tc()` - 11 edges
9. `TestFunctionOutputShape` - 11 edges
10. `TestValidateRouterOutput` - 10 edges

## Surprising Connections (you probably didn't know these)
- `load()` --calls--> `getBudgetStatus()`  [INFERRED]
  frontend/src/components/BudgetPanel/BudgetPanel.tsx → frontend/src/api/client.ts
- `handleSmartSubmit()` --calls--> `parseNatural()`  [INFERRED]
  frontend/src/components/TransactionForm/TransactionForm.tsx → frontend/src/api/client.ts
- `test_prefilter_catches()` --calls--> `_is_obviously_out_of_scope()`  [INFERRED]
  backend/tests/test_ai_routing.py → backend/core/ai_engine.py
- `test_in_scope_not_caught()` --calls--> `_is_obviously_out_of_scope()`  [INFERRED]
  backend/tests/test_ai_routing.py → backend/core/ai_engine.py
- `_run_tc()` --calls--> `get_llm_stats()`  [INFERRED]
  backend/tests/test_chat_backtest.py → backend/core/ai_engine.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (57): _answer_in_perimeter(), build_compact_context(), build_context(), chat_with_ai(), _dates(), _fn_anomalies(), _fn_budget_status(), _fn_category_drill() (+49 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (49): BaseModel, get_llm_stats(), Ritorna le statistiche sulle chiamate LLM dall'avvio del processo., ChatHistory, Transaction, BudgetCreate, BudgetResponse, ChatRequest (+41 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (32): execute_prebuilt_function(), _is_obviously_out_of_scope(), Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM., Normalizza e clippa l'output di ogni funzione prebuilt prima di ritornarlo., _validate_function_output(), Test harness per il motore AI: routing, pre-filtro OOS, guardrails input, shape, Tutte le query OOS devono essere bloccate prima di chiamare il LLM., Ogni funzione prebuilt deve rispettare i contratti di output. (+24 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (17): createBudget(), deleteBudget(), deleteTransaction(), downloadMonthlyReport(), exportTransactionsCsv(), getBudgetStatus(), parseNatural(), updateTransaction() (+9 more)

### Community 4 - "Community 4"
Cohesion: 0.09
Nodes (25): Azzera i contatori LLM. Usato dal test harness prima di ogni caso., _reset_llm_stats(), _ef(), _extract_fn_names(), _extract_routing(), _fn_matches(), _generate_report(), _needs_api() (+17 more)

### Community 5 - "Community 5"
Cohesion: 0.13
Nodes (10): createTransaction(), sendChat(), ChartErrorBoundary, handleSend(), retryAsText(), toggleVoice(), handleManualSubmit(), handleSmartSubmit() (+2 more)

### Community 6 - "Community 6"
Cohesion: 0.11
Nodes (13): lifespan(), Base, _fn_period_compare(), Budget, init_db(), budget_status(), create_budget(), _build_narrative() (+5 more)

### Community 7 - "Community 7"
Cohesion: 0.12
Nodes (11): _input_too_long(), Ritorna True se la domanda supera i limiti di lunghezza., Stringa vuota → _input_too_long=False (è un caso speciale, gestito da chat.py)., 1500 caratteri → _input_too_long=True., Più di 80 spazi (>81 parole) → _input_too_long=True., Domanda normale → non troppo lunga., MAX_QUESTION_CHARS deve essere 500., chat_with_ai con 1500 char → risposta di lunghezza-troppo-lunga (no eccezione). (+3 more)

### Community 8 - "Community 8"
Cohesion: 0.23
Nodes (5): Sanitizza i parametri di una singola funzione prebuilt (clip + whitelist)., Valida l'output del router LLM: produce use_functions (lista, max 3) + in_perime, _sanitize_params(), _validate_router_output(), TestValidateRouterOutput

### Community 9 - "Community 9"
Cohesion: 0.32
Nodes (1): TestWhatIfValidation

### Community 10 - "Community 10"
Cohesion: 0.22
Nodes (2): fmtMonthKey(), getCategoryMoM()

### Community 11 - "Community 11"
Cohesion: 0.43
Nodes (3): Taglia la history a MAX_HISTORY_MESSAGES e trunca i messaggi lunghi., _sanitize_history(), TestSanitizeHistory

### Community 12 - "Community 12"
Cohesion: 0.29
Nodes (6): anomalies(), anomaly_detail(), briefing(), Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h., Anomalie multi-tipo (5 detector) sugli ultimi 60-90gg.     Eseguito in thread po, Dettaglio statistico completo per una singola anomalia (calcolato on-demand).

### Community 13 - "Community 13"
Cohesion: 0.47
Nodes (3): _build_multi_summary(), Concatena blocchi; tronca proporzionalmente se supera MAX_MULTI_SUMMARY_CHARS., TestBuildMultiSummary

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (2): useChartColors(), useIsDark()

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): _is_obviously_out_of_scope deve ritornare True per ogni query OOS.

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): chat_with_ai su query OOS non deve fare nessuna chiamata al client LLM.

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Le query finanziarie non devono essere bloccate dal pre-filter.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Output deve sempre avere chart_data e table_data (anche se None).

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Se chart_data presente → data ≤ MAX_CHART_POINTS e type valido.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Se table_data presente → rows ≤ MAX_TABLE_ROWS e celle sono str.

## Knowledge Gaps
- **67 isolated node(s):** `True se l'input non contiene abbastanza caratteri alfabetici per essere una doma`, `Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM.`, `Ritorna True se la domanda supera i limiti di lunghezza.`, `Wrapper LLM centralizzato con contatore chiamate e json_mode con fallback.`, `Ritorna le statistiche sulle chiamate LLM dall'avvio del processo.` (+62 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 9`** (12 nodes): `TestWhatIfValidation`, `._route()`, `.test_horizon_months_clipped_high()`, `.test_horizon_months_clipped_low()`, `.test_invalid_category_nulled()`, `.test_monthly_delta_clipped_high()`, `.test_monthly_delta_clipped_low()`, `.test_monthly_target_clipped()`, `.test_monthly_target_zero_floor()`, `.test_percent_change_clipped_high()`, `.test_percent_change_clipped_low()`, `.test_valid_category_kept()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 10`** (10 nodes): `analyticsUtils.ts`, `fmtMonthKey()`, `getAvailableMonths()`, `getCalendarData()`, `getCategoryData()`, `getCategoryMoM()`, `getCategoryVolatility()`, `getMonthlyTrend()`, `getRecurringData()`, `getTimeOfDayData()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (3 nodes): `useTheme.ts`, `useChartColors()`, `useIsDark()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `_is_obviously_out_of_scope deve ritornare True per ogni query OOS.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `chat_with_ai su query OOS non deve fare nessuna chiamata al client LLM.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Le query finanziarie non devono essere bloccate dal pre-filter.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Output deve sempre avere chart_data e table_data (anche se None).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Se chart_data presente → data ≤ MAX_CHART_POINTS e type valido.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Se table_data presente → rows ≤ MAX_TABLE_ROWS e celle sono str.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `chat_with_ai()` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`, `Community 7`, `Community 13`?**
  _High betweenness centrality (0.154) - this node is a cross-community bridge._
- **Why does `chat()` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `Transaction` connect `Community 1` to `Community 6`?**
  _High betweenness centrality (0.076) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `Transaction` (e.g. with `Seed di dati realistici per il backtest del motore chat AI. Idempotente: elimina` and `Cancella e reinserisce le transazioni di test. Ritorna il numero di righe inseri`) actually correct?**
  _`Transaction` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `chat_with_ai()` (e.g. with `_run_tc()` and `test_zero_llm_calls()`) actually correct?**
  _`chat_with_ai()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 11 inferred relationships involving `execute_prebuilt_function()` (e.g. with `test_keys_always_present()` and `test_chart_data_bounds()`) actually correct?**
  _`execute_prebuilt_function()` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `True se l'input non contiene abbastanza caratteri alfabetici per essere una doma`, `Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM.`, `Ritorna True se la domanda supera i limiti di lunghezza.` to the rest of the system?**
  _67 weakly-connected nodes found - possible documentation gaps or missing edges._