# Graph Report - copilota-finanziario  (2026-05-04)

## Corpus Check
- 49 files · ~48,288 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 456 nodes · 735 edges · 28 communities detected
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 215 edges (avg confidence: 0.63)
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
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]

## God Nodes (most connected - your core abstractions)
1. `Transaction` - 37 edges
2. `_q()` - 26 edges
3. `_dates()` - 24 edges
4. `chat_with_ai()` - 17 edges
5. `TransactionCreate` - 15 edges
6. `TransactionResponse` - 15 edges
7. `TransactionUpdate` - 15 edges
8. `execute_prebuilt_function()` - 14 edges
9. `_validate_router_output()` - 14 edges
10. `Budget` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Transaction` --uses--> `Run migrations in 'offline' mode.      This configures the context with just a U`  [INFERRED]
  backend/core/database.py → alembic/env.py
- `Transaction` --uses--> `Run migrations in 'online' mode.`  [INFERRED]
  backend/core/database.py → alembic/env.py
- `Transaction` --uses--> `In this scenario we need to create an Engine     and associate a connection with`  [INFERRED]
  backend/core/database.py → alembic/env.py
- `execute_prebuilt_function()` --calls--> `test_chart_data_bounds()`  [INFERRED]
  backend/core/ai_engine.py → backend/tests/test_ai_routing.py
- `execute_prebuilt_function()` --calls--> `test_table_data_bounds()`  [INFERRED]
  backend/core/ai_engine.py → backend/tests/test_ai_routing.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (58): _answer_in_perimeter(), build_compact_context(), build_context(), chat_with_ai(), _dates(), _detect_anomalies_for_transactions(), _fn_anomalies(), _fn_budget_status() (+50 more)

### Community 1 - "Community 1"
Cohesion: 0.1
Nodes (48): BaseModel, invalidate_anomaly_cache(), Invalida cache per un utente.     Se year/month specificati, invalida solo quel, Transaction, BudgetCreate, BudgetResponse, Config, DashboardResponse (+40 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (18): createBudget(), deleteBudget(), deleteTransaction(), downloadMonthlyReport(), exportTransactionsCsv(), generateMonthlyReportWithAnomalies(), getBudgetStatus(), parseNatural() (+10 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (29): do_run_migrations(), Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode., In this scenario we need to create an Engine     and associate a connection with, run_async_migrations(), run_migrations_offline(), run_migrations_online(), lifespan() (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (30): Azzera i contatori LLM. Usato dal test harness prima di ogni caso., _reset_llm_stats(), _d(), Seed di dati realistici per il backtest del motore chat AI. Idempotente: elimina, Cancella e reinserisce le transazioni di test. Ritorna il numero di righe inseri, seed_backtest_db(), _ef(), _extract_fn_names() (+22 more)

### Community 5 - "Community 5"
Cohesion: 0.08
Nodes (22): _is_obviously_out_of_scope(), Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM., Taglia la history a MAX_HISTORY_MESSAGES e trunca i messaggi lunghi., _sanitize_history(), Test harness per il motore AI: routing, pre-filtro OOS, guardrails input, shape, Tutte le query OOS devono essere bloccate prima di chiamare il LLM., Ogni query OOS deve essere catturata dal pre-filter regex., Nessuna query finanziaria deve essere bloccata dal pre-filter. (+14 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (16): execute_prebuilt_function(), Normalizza e clippa l'output di ogni funzione prebuilt prima di ritornarlo., _validate_function_output(), Ogni funzione prebuilt deve rispettare i contratti di output., n=9999 deve essere clippato a MAX_TOP_N=50 senza eccezioni., period_days=10000 deve essere clippato a MAX_PERIOD_DAYS=365., Funzione inesistente → {chart_data: None, table_data: None} senza eccezione., _validate_function_output clippa data a MAX_CHART_POINTS. (+8 more)

### Community 7 - "Community 7"
Cohesion: 0.13
Nodes (10): createTransaction(), sendChat(), ChartErrorBoundary, handleSend(), retryAsText(), toggleVoice(), handleManualSubmit(), handleSmartSubmit() (+2 more)

### Community 8 - "Community 8"
Cohesion: 0.16
Nodes (14): _count_anomalies_by_type(), _fn_period_compare(), get_anomalies_for_month(), Count anomalies by detection_type., FUNZIONE UNICA per ottenere anomalie di un mese.     Usata da dashboard, report,, _build_narrative(), _build_pdf(), _fmt_eur() (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (9): Stringa vuota → _input_too_long=False (è un caso speciale, gestito da chat.py)., 1500 caratteri → _input_too_long=True., Più di 80 spazi (>81 parole) → _input_too_long=True., Domanda normale → non troppo lunga., MAX_QUESTION_CHARS deve essere 500., chat_with_ai con 1500 char → risposta di lunghezza-troppo-lunga (no eccezione)., Messaggio vuoto → la logica route produrrebbe HTTPException 400.          Testat, Messaggio con soli spazi → stessa logica porta a HTTPException 400. (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.23
Nodes (5): Sanitizza i parametri di una singola funzione prebuilt (clip + whitelist)., Valida l'output del router LLM: produce use_functions (lista, max 3) + in_perime, _sanitize_params(), _validate_router_output(), TestValidateRouterOutput

### Community 11 - "Community 11"
Cohesion: 0.32
Nodes (1): TestWhatIfValidation

### Community 12 - "Community 12"
Cohesion: 0.22
Nodes (2): fmtMonthKey(), getCategoryMoM()

### Community 13 - "Community 13"
Cohesion: 0.22
Nodes (8): anomaly_detail(), briefing(), list_anomalies(), Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h., Ritorna anomalie del mese corrente.     Usa cache in memoria se disponibile., Utente clicca 'Refresh anomalies'.     Ricalcola con force_refresh=True per il m, Dettaglio statistico completo per una singola anomalia (calcolato on-demand) — f, refresh_anomalies()

### Community 14 - "Community 14"
Cohesion: 0.29
Nodes (2): refreshAnomalies(), async()

### Community 15 - "Community 15"
Cohesion: 0.47
Nodes (3): _build_multi_summary(), Concatena blocchi; tronca proporzionalmente se supera MAX_MULTI_SUMMARY_CHARS., TestBuildMultiSummary

### Community 16 - "Community 16"
Cohesion: 0.4
Nodes (3): Add user_id columns for multi-tenancy  Revision ID: f6b8b3ac0842 Revises: Create, Upgrade schema - Add user_id columns for multi-tenancy., upgrade()

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (2): useChartColors(), useIsDark()

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): _is_obviously_out_of_scope deve ritornare True per ogni query OOS.

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): chat_with_ai su query OOS non deve fare nessuna chiamata al client LLM.

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Le query finanziarie non devono essere bloccate dal pre-filter.

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Output deve sempre avere chart_data e table_data (anche se None).

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Se chart_data presente → data ≤ MAX_CHART_POINTS e type valido.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Se table_data presente → rows ≤ MAX_TABLE_ROWS e celle sono str.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Dettaglio statistico completo per una singola anomalia (calcolato on-demand).

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Anomalie multi-tipo (5 detector) sugli ultimi 60-90gg.     Eseguito in thread po

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Dettaglio statistico completo per una singola anomalia (calcolato on-demand).

## Knowledge Gaps
- **78 isolated node(s):** `True se l'input non contiene abbastanza caratteri alfabetici per essere una doma`, `Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM.`, `Ritorna True se la domanda supera i limiti di lunghezza.`, `Wrapper LLM centralizzato con contatore chiamate e json_mode con fallback.`, `Ritorna le statistiche sulle chiamate LLM dall'avvio del processo.` (+73 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (12 nodes): `TestWhatIfValidation`, `._route()`, `.test_horizon_months_clipped_high()`, `.test_horizon_months_clipped_low()`, `.test_invalid_category_nulled()`, `.test_monthly_delta_clipped_high()`, `.test_monthly_delta_clipped_low()`, `.test_monthly_target_clipped()`, `.test_monthly_target_zero_floor()`, `.test_percent_change_clipped_high()`, `.test_percent_change_clipped_low()`, `.test_valid_category_kept()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 12`** (10 nodes): `analyticsUtils.ts`, `fmtMonthKey()`, `getAvailableMonths()`, `getCalendarData()`, `getCategoryData()`, `getCategoryMoM()`, `getCategoryVolatility()`, `getMonthlyTrend()`, `getRecurringData()`, `getTimeOfDayData()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 14`** (7 nodes): `refreshAnomalies()`, `async()`, `fmt()`, `getLevel()`, `StatCell()`, `yFmt()`, `Dashboard.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (3 nodes): `useTheme.ts`, `useChartColors()`, `useIsDark()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `_is_obviously_out_of_scope deve ritornare True per ogni query OOS.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `chat_with_ai su query OOS non deve fare nessuna chiamata al client LLM.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Le query finanziarie non devono essere bloccate dal pre-filter.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Output deve sempre avere chart_data e table_data (anche se None).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Se chart_data presente → data ≤ MAX_CHART_POINTS e type valido.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Se table_data presente → rows ≤ MAX_TABLE_ROWS e celle sono str.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Dettaglio statistico completo per una singola anomalia (calcolato on-demand).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Briefing AI giornaliero con 3 insight e un'azione consigliata. Cache 1h.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Anomalie multi-tipo (5 detector) sugli ultimi 60-90gg.     Eseguito in thread po`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Dettaglio statistico completo per una singola anomalia (calcolato on-demand).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Transaction` connect `Community 1` to `Community 8`, `Community 3`, `Community 4`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **Why does `chat_with_ai()` connect `Community 0` to `Community 3`, `Community 4`, `Community 5`, `Community 6`, `Community 9`, `Community 15`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `invalidate_anomaly_cache()` connect `Community 1` to `Community 0`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Are the 35 inferred relationships involving `Transaction` (e.g. with `Seed di dati realistici per il backtest del motore chat AI. Idempotente: elimina` and `Cancella e reinserisce le transazioni di test. Ritorna il numero di righe inseri`) actually correct?**
  _`Transaction` has 35 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `chat_with_ai()` (e.g. with `_run_tc()` and `test_zero_llm_calls()`) actually correct?**
  _`chat_with_ai()` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 13 inferred relationships involving `TransactionCreate` (e.g. with `NLParseRequest` and `Crea una nuova transazione.`) actually correct?**
  _`TransactionCreate` has 13 INFERRED edges - model-reasoned connections that need verification._
- **What connects `True se l'input non contiene abbastanza caratteri alfabetici per essere una doma`, `Ritorna True se la domanda corrisponde a un dominio OOS senza chiamare l'LLM.`, `Ritorna True se la domanda supera i limiti di lunghezza.` to the rest of the system?**
  _78 weakly-connected nodes found - possible documentation gaps or missing edges._