# AGENTS.md — FinCopilot

Guida operativa per agenti di coding che lavorano su questa repo.
Leggere questo file prima di toccare codice. Il backlog attivo è in `BACKLOG.md`.

---

## 1. Cos'è il progetto

**FinCopilot** è un'app web di finanza personale con assistente AI in italiano.
L'utente registra spese (testo, voce, manuale, import da estratto conto), definisce
budget e interroga i propri dati in linguaggio naturale. La risposta è accompagnata
da tabella e grafico.

- **Produzione:** backend su Render, frontend su Vercel, DB/Auth su Supabase.
- **Demo:** https://copilot-finanziario-ten.vercel.app
- **Repo:** https://github.com/Rbiagetti/Copilot-finanziario
- **Lingua:** UI, commenti, messaggi di commit e documentazione sono in italiano.
- **Utente reale:** l'app è usata dall'autore con dati veri. Ogni regressione sui
  calcoli (date, importi, filtri) è considerata grave.

---

## 2. Comandi rapidi

Tutti i comandi vanno eseguiti dalla **root della repo** (i path SQLite sono relativi).

```bash
# Backend
source venv/bin/activate                  # Python 3.11 — NON usare il python3 di sistema (3.9)
pip install -r requirements.txt
uvicorn backend.main:app --reload         # http://localhost:8000  (docs su /docs)

# Frontend (secondo terminale)
cd frontend
npm install
npm run dev                               # http://localhost:5173

# Test deterministici (nessuna API key richiesta)
# Nota: se GROQ_API_KEY è esportata nella shell, test_ai_routing esegue anche i test
# che chiamano il modello. Per la sola parte deterministica:
env -u GROQ_API_KEY pytest backend/tests/test_ai_routing.py backend/tests/test_import_engine.py backend/tests/test_wealth.py -v

# Backtest conversazionale della chat (richiede GROQ_API_KEY, costa token)
pytest backend/tests/test_chat_backtest.py -v -s

# Seed dati di esempio (90 transazioni)
python -m backend.tests.seed_test_data

# Controlli frontend
cd frontend && npm run lint && npm run build

# Controllo sintattico rapido backend
python -m py_compile backend/core/ai_engine.py backend/api/routes/*.py
```

> Se `SUPABASE_URL` è vuota il backend disattiva l'autenticazione e usa un utente
> di sviluppo: è la modalità normale per lavorare in locale.

---

## 3. Mappa del codice

```
backend/
  main.py                     # FastAPI app, CORS, registrazione router, /health
  api/
    auth.py                   # get_current_user: verifica JWT Supabase → user_id
    models/schemas.py         # schemi Pydantic + CATEGORIES (10 standard)
    routes/
      transactions.py         # CRUD, count, date-bounds, export CSV, bulk-delete
      analytics.py            # full-history, dashboard, forecast, monthly-history
      chat.py                 # POST /chat, history, stats
      budgets.py              # CRUD budget + /status
      ai.py                   # briefing
      import_data.py          # /import/preview, /import/commit (stateless)
      categories.py           # standard + custom per utente (soft delete)
      wealth.py               # patrimonio: conti + snapshot + overview
      settings.py             # modello AI per utente
      report.py               # report mensile PDF (reportlab)
  core/
    ai_engine.py              # ⚠️ cuore del progetto, ~2.200 righe
    categories.py             # fonte unica categorie standard + custom per utente
    import_engine.py          # parsing CSV/XLSX/PDF, mapping colonne, date
    database.py               # engine SQLAlchemy, modelli, init_db
                              # (Transaction, Budget, Category, WealthAccount,
                              #  WealthSnapshot, ChatHistory, UserSettings)
    auth.py                   # helper JWT (duplicato parziale di api/auth.py)
  tests/
    test_ai_routing.py        # routing deterministico, no LLM
    test_import_engine.py     # regressioni parsing/date/import
    test_wealth.py            # conti, snapshot, overview, isolamento utenti
    test_chat_backtest.py     # 60 casi conversazionali (LLM reale)
    seed_test_data.py         # 90 transazioni realistiche

frontend/src/
  App.tsx                     # routing e layout
  api/client.ts               # tutte le chiamate HTTP + token Supabase
  store/appStore.ts           # stato globale (vista, filtri, cache)
  store/authStore.ts          # sessione
  components/                 # una cartella per area (Dashboard, Chat, Budget,
                              #  Wealth, TransactionList, Settings, ...)
  styles/                     # CSS per area: base, layout, dashboard, chat,
                              # transactions, budget, components, legal, utilities
  hooks/                      # useBodyScrollLock, useFocusTrap, useChartColors
  lib/                        # supabase client, icone categorie, confirm dialog
```

**File più grandi / delicati:** `backend/core/ai_engine.py` (2.237 righe),
`frontend/src/components/TransactionList/TransactionList.tsx` (825),
`backend/api/routes/report.py` (613), `ChatInterface.tsx` (562),
`backend/core/import_engine.py` (448).

---

## 4. Motore AI — regole da non violare

`backend/core/ai_engine.py` è il componente più delicato. Architettura:

1. **Pre-filtro** deterministico (`_is_obviously_out_of_scope`, `_input_meaningless`,
   `_input_too_long`): le domande fuori perimetro non chiamano il modello.
2. **Router LLM** (`_select_function`) con `FUNCTION_SELECTOR_PROMPT`: il modello
   **non genera SQL**, restituisce JSON con `use_functions: [{name, params}]`
   (1..N funzioni) e `in_perimeter`.
3. **Validazione** (`_sanitize_params`, `_validate_router_output`): nomi funzione
   solo dal `FUNCTION_CATALOG`, parametri con bound (`MAX_PERIOD_DAYS`,
   `MAX_TOP_N`, `MAX_CHART_POINTS`, `MAX_TABLE_ROWS`, ...).
4. **Esecuzione** (`execute_prebuilt_function`) delle funzioni `_fn_*`, ognuna
   **sempre filtrata per `user_id`**.
5. **Interpretazione** finale (`_interpret_results`) con temperatura 0 e limiti
   su righe/tabella/punti grafico.

Regole pratiche:

- **Mai** aggiungere SQL libero generato dal modello.
- Ogni nuova funzione va registrata in `FUNCTION_CATALOG` con schema parametri,
  bound e descrizione: il router la vede solo da lì.
- Ogni `_fn_*` deve accettare `user_id` come primo argomento e filtrare su di esso.
- **Categorie:** la fonte unica è `backend/core/categories.py`. Le standard sono 11
  (incluso `intrattenimento`); le personalizzate si uniscono per utente con
  `get_active_category_names()`. La chat carica le categorie attive all'inizio di
  `chat_with_ai()` e le passa al router + a un `ContextVar` per-request: non
  reintrodurre liste hardcoded né variabili globali mutabili.
- Determinismo: temperatura 0, seed fisso, JSON forzato. Non introdurre casualità.
- Le risposte devono restare in italiano e includere tabelle/grafici quando utili.
- Variabili di debug: `AI_DEBUG_ROUTING=1`, `AI_DISABLE_LLM=1` (risposta OOS
  immediata, utile per testare la UI senza costi), `AI_FORCE_TEMP_ZERO=1`.

Funzioni attualmente esposte (15): `query_spending`, `month_vs_month`,
`year_end_forecast`, `budget_status`, `recurring_vs_variable`,
`subscriptions_audit`, `category_volatility`, `frequency_analysis`,
`concentration_risk`, `period_compare`, `momentum`, `search_transactions`,
`category_drill`, `tag_analysis`, `what_if`.

---

## 5. Wealth Monitor (patrimonio)

Modulo `backend/api/routes/wealth.py` + `frontend/src/components/Wealth/WealthPanel.tsx`.

- **Modello:** `wealth_accounts` (conti configurabili) e `wealth_snapshots` (saldo per
  conto e data ISO). Vincolo univoco `(account_id, snapshot_date)` → il salvataggio è
  un **upsert idempotente**.
- **Semantica:** una "foto" è l'insieme degli snapshot della stessa data; il patrimonio
  è la **somma delle attività** (nessuna passività in v1).
- **Archiviazione:** `DELETE /wealth/accounts/{id}` è soft delete. Il conto sparisce da
  form, totali e composizione; gli snapshot restano in DB ma non vengono più conteggiati.
- **Date:** la foto non può essere nel futuro (`422`). Il prefill usa l'ultimo saldo
  **≤ data scelta**.
- **Overview:** serie limitata a `months` (default 12, max 60); saldo e delta per conto
  usano invece lo storico completo, così un conto aggiornato fuori finestra non sparisce.
- **Frontend:** aggiungere una view richiede 4 punti allineati — `View` in
  `appStore.ts`, `validViews` in `appStore.ts` e `App.tsx`, `NAV_ITEMS` in `Sidebar.tsx`
  e `TITLES` in `TopBar.tsx`.
- **Mobile:** la bottom nav ha 6 voci (icone 20px, `flex: 1 1 0`): ci stanno a 375px.
  Se se ne aggiunge una settima, ridurre icona/gap in `layout.css`.

---

## 6. Dati e multi-tenancy

- Ogni tabella ha `user_id` (UUID Supabase) e ogni query deve filtrarlo.
- Lo schema è versionato con Alembic (`alembic/versions/`).
- Il campo `date` è una **stringa ISO** (`YYYY-MM-DD`): i confronti sono lessicografici.
  Quando si filtra un periodo, **escludere sempre il futuro** (`date <= today`):
  in passato transazioni future hanno falsato "ultimi N giorni" e "questo mese".
- Transazioni: `amount, category, subcategory, description, date, time, account,
  tags, source, is_recurring, created_at, updated_at`.
- `source="backtest"` identifica i dati di test: il seed li cancella e ricrea.
- Il DB locale è `data/fincopilot.db` (gitignored). Non committare mai `.db`, `.env`,
  `test_isolation.db`.

---

## 7. Frontend

- **Solo tema scuro.** Il toggle chiaro/scuro è stato rimosso: non reintrodurlo
  senza richiesta esplicita.
- I colori dei grafici Recharts arrivano da `useChartColors()`
  (`frontend/src/hooks/useTheme.ts`): Recharts non legge le CSS custom properties.
- Stato globale in Zustand (`appStore`, `authStore`); niente prop drilling profondo.
- CSS diviso per area in `frontend/src/styles/`; aggiungere regole nel file dell'area,
  non in `base.css`, e usare le variabili già definite.
- Mobile-first: breakpoint 768px e 480px, barra di navigazione inferiore, safe area iOS.
- Le chiamate HTTP passano tutte da `src/api/client.ts` con token Bearer.
- Il markdown della chat è renderizzato da un renderer custom in `ChatInterface.tsx`
  (non una libreria): se cambi il formato delle risposte backend, verifica anche quello.

---

## 8. Test

| File | Cosa copre | LLM |
|---|---|---|
| `test_ai_routing.py` | routing, validazione parametri, bound, funzioni | no |
| `test_import_engine.py` | CSV/XLSX/PDF, date italiane/ISO, dedup, preamboli | no |
| `test_wealth.py` | conti, snapshot/upsert, overview, isolamento utenti | no |
| `test_chat_backtest.py` | 60 domande reali, report HTML | sì |

Regola: ogni modifica al motore AI o all'import va accompagnata da almeno un test
deterministico di regressione. Prima di un commit, eseguire i test `no_llm`.

---

## 9. Deploy

- **Backend:** Render, `render.yaml`, start `uvicorn backend.main:app`.
  Env richieste: `DATABASE_URL`, `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `CORS_ORIGINS`.
- **Frontend:** Vercel, build `npm run build`, env `VITE_API_URL`,
  `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
- **DB/Auth:** Supabase. Le tabelle hanno RLS attiva senza policy per il ruolo
  pubblico: l'accesso avviene solo dal backend con service/DB URL.
- GitHub Action `keep-alive.yml` pinga `/api/v1/health` ogni 5 minuti.
- Dopo un push su `master`, il deploy parte automaticamente. Verificare sempre
  `/api/v1/health` e una chiamata reale prima di dichiarare "fatto".

---

## 10. Trappole note

1. **Python sbagliato:** `python3` di sistema è 3.9; il progetto richiede 3.11.
   Usare `source venv/bin/activate` o `./venv/bin/python`.
2. **Categorie:** fonte unica in `backend/core/categories.py` (11 standard, incluso
   `intrattenimento`). `schemas.py` e `ai_engine.py` importano da lì. La chat vede
   anche le personalizzate via `ContextVar` per-request. Se aggiungi una categoria
   standard, toccala **solo** in `core/categories.py` e aggiorna il fallback in
   `frontend/src/store/appStore.ts`.
3. **Date:** mai fidarsi del parsing implicito di `dateutil`. Formati italiani
   abbreviati (`gen`, `feb`) e ISO hanno già causato corruzione silenziosa dei dati.
4. **Import stateless:** `/import/preview` e `/import/commit` ricevono entrambi il
   file; non introdurre stato server-side tra le due chiamate.
5. **`rate_limit.py` non esiste più** (ne resta solo il `.pyc`): i limiti attuali
   sono dentro `import_engine.py` (max 5 MB, max 1000 righe). Il limite
   "3 import/giorno per utente" non è implementato.
6. **Anomalie rimosse dall'UI** (commit `d18ac71`): non reintrodurle senza richiesta.
7. **`.claude/settings.json`** contiene configurazione `ruflo`/agent-teams usata in
   passato da Claude Code: non è necessaria per lavorare e non va estesa.
8. **Segreti:** `.env` è presente in locale ma gitignored. Non stamparne il contenuto
   nei log e non committarlo.
9. **`TestClient` non funziona in questo venv:** starlette e `httpx==0.28.1` sono
   incompatibili (`Client.__init__() got an unexpected keyword argument 'app'`).
   I test chiamano le funzioni di route direttamente, con una sessione SQLite in
   memoria (`test_wealth.py` è l'esempio da copiare per i nuovi moduli).
10. **`GROQ_API_KEY` spesso esportata nella shell:** i test marcati `requires_api`
    partono davvero e possono andare in timeout. Per la suite deterministica usare
    `env -u GROQ_API_KEY pytest ...`.
11. **Tabelle in dev/prod:** `init_db()` (`Base.metadata.create_all`) crea le tabelle
    all'avvio, anche sul Postgres di Supabase puntato da `.env`. La migrazione Alembic
    resta la fonte di verità per i deploy: aggiungerla sempre per le tabelle nuove.

---

## 11. Workflow di lavoro consigliato

Il modo di lavorare che ha funzionato su questo progetto:

1. **Leggere `BACKLOG.md`** e scegliere il task; non mescolare task diversi nella
   stessa modifica.
2. **Scrivere prima la specifica**: obiettivo, file esatti da toccare, blocchi
   numerati, criteri di verifica. Evita modifiche esplorative su `ai_engine.py`.
3. **Implementare a blocchi piccoli**, verificando con `py_compile`/`lint` a ogni passo.
4. **Test deterministici** (`no_llm`) + verifica manuale in locale su backend e
   frontend (viewport mobile inclusa).
5. **Commit in italiano**, messaggio che spiega il *perché*; un commit per tema.
6. **Push su `master`** e verifica del deploy.
7. **Aggiornare `BACKLOG.md`** spuntando il task e annotando commit/gap residui.

Prima di modificare aree già toccate di recente, controllare `git log --oneline -20`
e `git diff` rispetto a `origin/master`: su questo progetto sono già stati fatti
refactor ampi e il rischio di regressioni silenziose è reale.
