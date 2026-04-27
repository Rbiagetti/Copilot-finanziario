![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.11x-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)

# FinCopilot — Copilota Finanziario AI

Applicazione web per la gestione delle finanze personali con un assistente AI conversazionale.
Registra spese, monitora budget, visualizza trend e interroga i tuoi dati in linguaggio naturale.
Pensato per uso personale: si avvia in 5 minuti su qualsiasi macchina con Python e Node.

---

## Stack

| Layer | Tecnologia |
|---|---|
| Backend | FastAPI · SQLAlchemy · SQLite (dev) |
| AI | Groq API · Llama 3.3 70B · prompt engineering custom |
| Frontend | React 18 · Vite · TypeScript |
| Stato | Zustand |
| Grafici | Recharts |
| Auth | Supabase (JWT) |
| Deploy | Render.com (backend) · Vercel (frontend) |

---

## Prerequisiti

- Python >= 3.11
- Node >= 18
- Account [Groq](https://console.groq.com) gratuito per la API key
- Account [Supabase](https://supabase.com) gratuito per l'autenticazione

---

## Setup in 5 minuti

```bash
# 1. Clone
git clone https://github.com/Rbiagetti/Copilot-finanziario.git
cd Copilot-finanziario

# 2. Backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # poi edita con le tue chiavi (vedi sezione Env)
uvicorn backend.main:app --reload
# API disponibile su http://localhost:8000
# Docs interattive su http://localhost:8000/docs

# 3. Frontend (nuovo terminale)
cd frontend
cp .env.example .env              # già preconfigurato per localhost
npm install
npm run dev
# App disponibile su http://localhost:5173
```

---

## Variabili d'ambiente

### Backend — `.env` (root)

```env
# Obbligatoria — ottienila su https://console.groq.com
GROQ_API_KEY=gsk_...

# DB locale (default: SQLite, non modificare per sviluppo)
DATABASE_URL=sqlite:///./data/fincopilot.db

# Supabase — per validare i JWT in arrivo dal frontend
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...

# Debug opzionali
AI_DEBUG_ROUTING=0      # 1 = log routing AI in console
AI_DISABLE_LLM=0        # 1 = disabilita chiamate Groq (mock responses)
```

### Frontend — `frontend/.env`

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_SUPABASE_URL=https://xxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
```

Copia `frontend/.env.example` → `frontend/.env` e compila con le stesse credenziali Supabase.

---

## Come eseguire i test

```bash
# Attiva venv se non attivo
source venv/bin/activate

# Test deterministici — non richiedono GROQ_API_KEY
pytest backend/tests/test_ai_routing.py -v

# Backtesting conversazionale — richiede GROQ_API_KEY nel .env
pytest backend/tests/test_chat_backtest.py -v -s

# Report HTML del backtest (generato automaticamente dopo il run)
open backend/tests/backtest_report.html
```

---

## Reset del DB di sviluppo

```bash
# Elimina il DB locale e ricrealo da zero (SQLite)
rm -f data/fincopilot.db
uvicorn backend.main:app --reload   # le tabelle vengono ricreate all'avvio

# Carica dati di test realistici (90 transazioni, 3 mesi)
python -m backend.tests.seed_test_data
```

---

## Struttura del progetto

```
fincopilot/
├── backend/
│   ├── api/
│   │   ├── models/          # Pydantic schemas (request/response)
│   │   └── routes/          # FastAPI routers: chat, transactions, analytics, budgets, ai
│   ├── core/                # Logica di business: ai_engine, database, auth
│   ├── tests/               # Test suite e seed data
│   └── main.py              # Entry point FastAPI
├── frontend/
│   ├── src/
│   │   ├── api/             # Client HTTP Axios + tipi TypeScript
│   │   ├── components/      # Componenti React (una cartella per componente)
│   │   ├── hooks/           # Custom hooks (useTheme, useFocusTrap)
│   │   ├── lib/             # Client Supabase
│   │   ├── store/           # Zustand global store
│   │   ├── styles/          # CSS modulari per area
│   │   └── utils/           # Utilities (voiceService, analyticsUtils)
│   └── index.html
├── data/                    # Solo schema SQL o seed statici — mai *.db
├── docs/                    # Documentazione tecnica (ai_engine.md, repo_audit.md)
├── .env.example             # Template variabili d'ambiente backend
├── requirements.txt
└── render.yaml              # Config deploy Render.com
```

---

## Funzionalità

- **Dashboard** — totale mese, trend giornaliero, top categorie, variazione mese precedente
- **Transazioni** — inserimento manuale, parsing linguaggio naturale, import, tag, export CSV
- **Budget** — limiti per categoria con alert visivi (ok / warning / over)
- **Chat AI** — 12+ funzioni analitiche (statistiche, ricerca merchant, anomalie, previsione, what-if)
- **Briefing giornaliero** — insight automatici all'apertura dell'app
- **ThinkingTrace** — traccia i passi di ragionamento dell'AI nella chat (collassabile)

---

## Roadmap

- [x] Fase 1 — Dashboard, inserimento manuale, budget
- [x] Fase 1 — Chat AI con routing multi-funzione
- [x] Fase 1 — Backtesting conversazionale (60 test case)
- [ ] Fase 2 — Import bancario automatico (CSV OFX/CAMT)
- [ ] Fase 2 — Multi-account e trasferimenti interni
- [ ] Fase 2 — Notifiche push budget superato

---

## Licenza

MIT © Roberto Biagetti
