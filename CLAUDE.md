# FinCopilot — Contesto per LLM

App di finanza personale con AI. Permette di tracciare spese, analizzarle via chat in linguaggio naturale e visualizzarle con grafici interattivi.

---

## Stack

| Layer | Tecnologia |
|-------|-----------|
| Backend | FastAPI + SQLAlchemy + SQLite |
| Frontend | React 18 + TypeScript + Vite |
| Charts | Recharts (BarChart, LineChart, PieChart) |
| AI | Groq API — modello `llama-3.3-70b-versatile` (interfaccia OpenAI-compatible) |
| Stile | CSS custom dark theme (no Tailwind) |

---

## Struttura del progetto

```
copilota-finanziario/
├── backend/
│   ├── main.py                  # FastAPI app entry point
│   ├── core/
│   │   ├── database.py          # SQLAlchemy models + get_db
│   │   └── ai_engine.py         # Pipeline AI: LLM → exec Python → chart JSON
│   └── api/
│       ├── models/schemas.py    # Pydantic schemas
│       └── routes/
│           ├── transactions.py  # CRUD transazioni
│           ├── chat.py          # POST /api/v1/chat/
│           ├── budgets.py       # CRUD budget
│           └── analytics.py     # Dashboard data
├── frontend/
│   └── src/
│       ├── api/client.ts        # Axios client per tutte le API
│       ├── components/
│       │   ├── Dashboard/       # KPI cards + 3 grafici + classifica categorie
│       │   ├── ChatInterface/   # Chat AI con grafici Recharts inline
│       │   ├── TransactionList/ # Lista + filtri spese
│       │   ├── TransactionForm/ # Form aggiunta spesa
│       │   └── BudgetPanel/     # Gestione budget per categoria
│       └── index.css            # Tutto il CSS (dark theme)
├── data/
│   └── fincopilot.db            # SQLite database (non committato)
├── backend/seed_test_data.py    # Genera dati di test realistici
├── backend/migrate_old_db.py    # Migrazione da schema vecchio
├── requirements.txt
├── Makefile                     # Comandi rapidi
└── .env                         # GROQ_API_KEY (non committato)
```

---

## Come avviare

**Prerequisiti:** Python 3.9+, Node 18+, chiave API Groq

```bash
# 1. Crea .env
echo "GROQ_API_KEY=tua_chiave" > .env

# 2. Backend
pip install -r requirements.txt
uvicorn backend.main:app --reload   # DALLA ROOT, non da backend/

# 3. Frontend (altro terminale)
cd frontend && npm install && npm run dev

# 4. (Opzionale) Seed dati di test
python backend/seed_test_data.py
```

Frontend: http://localhost:5173
Backend API docs: http://localhost:8000/docs

---

## Database

**File:** `data/fincopilot.db`
**Schema principale:**

```sql
transactions(
  id, amount REAL, category TEXT, subcategory TEXT,
  description TEXT, date TEXT, time TEXT,
  account TEXT, tags TEXT, source TEXT,
  created_at TEXT, updated_at TEXT
)
```

**Categorie valide:** cibo, trasporti, casa, salute, svago, abbigliamento, lavoro, abbonamenti, formazione, altro

---

## Pipeline AI (core del progetto)

`backend/core/ai_engine.py` — funzione principale: `chat_with_ai(question, history)`

1. **`build_context()`** — legge stats dal DB (totali, range date, categorie) e le inietta nel system prompt
2. **`generate_analytics()`** — chiama Groq LLM, riceve JSON con `{answer, python_code, followup_questions}`
3. **`execute_analysis_code()`** — esegue il codice Python generato con `exec()` in namespace controllato (`DB_PATH` iniettato)
4. Il codice AI stampa `CHART_DATA:{json}` su stdout → parsato e inviato al frontend
5. Il frontend renderizza il chart con Recharts (`ChatChart` component)

**Formato chart_data:**
```json
{"type": "bar|pie|line", "data": [{"name": "categoria", "value": 123.45}], "title": "Titolo"}
```

**Variabili disponibili nel namespace exec:**
- `DB_PATH` — path assoluto al SQLite
- `__builtins__` — built-in Python standard

**Regole critiche del system prompt:**
- NON usare `matplotlib`, `pandas`, `plt`
- SEMPRE `print("CHART_DATA:" + json.dumps(chart))`
- NON ridefinire `DB_PATH`
- `conn = sqlite3.connect(DB_PATH)` — già definito

---

## API principali

| Metodo | Endpoint | Descrizione |
|--------|----------|-------------|
| GET | `/api/v1/analytics/dashboard` | Dati dashboard (KPI, categorie, trend) |
| GET | `/api/v1/transactions/` | Lista transazioni (filtri: category, date_from, date_to) |
| POST | `/api/v1/transactions/` | Crea transazione |
| PUT | `/api/v1/transactions/{id}` | Aggiorna transazione |
| DELETE | `/api/v1/transactions/{id}` | Elimina transazione |
| POST | `/api/v1/chat/` | Chat AI — body: `{message, history}` |
| GET | `/api/v1/budgets/status` | Budget con % utilizzo |
| POST | `/api/v1/budgets/` | Crea budget |
| PUT | `/api/v1/budgets/{id}` | Aggiorna budget |

---

## Decisioni architetturali importanti

- **`uvicorn` va lanciato dalla root** — `DATABASE_URL` usa path relativo `./data/fincopilot.db`
- **Python 3.9 compat** — usa `Optional[X]` non `X | None`, `from __future__ import annotations`
- **Recharts invece di matplotlib** — migrazione completa, niente immagini base64
- **Pie chart** — usa `<Legend>` invece di `label` prop per evitare overlap su fette piccole
- **Bar chart** — `angle={-40}`, `textAnchor="end"`, `interval={0}` quando categorie > 6
- **Percentuali pie tooltip** — calcolate manualmente `value / total_month * 100`, NON da `props.payload.percent` (bug Recharts)
- **Filtro null chart** — items con `name: null/none/nan` filtrati in `execute_analysis_code()`
- **Groq rate limiting** — nei test metti `sleep(5-6)` tra query

---

## Cose da migliorare (backlog)

- Import CSV/PDF estratti conto bancario
- Notifiche push quando si supera il budget
- Confronto mese-su-mese più avanzato nella dashboard
- Esportazione dati (CSV/PDF report)
- Multi-account support
- Analisi predittiva fine mese più accurata
