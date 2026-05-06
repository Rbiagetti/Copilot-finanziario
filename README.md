![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-latest-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![License](https://img.shields.io/badge/license-MIT-green)
![Deploy](https://img.shields.io/badge/deploy-Render%20%2B%20Vercel-black)

# FinCopilot — Copilota Finanziario AI

Applicazione web per la gestione delle finanze personali con assistente AI conversazionale in italiano.
Registra spese, monitora budget, analizza trend e interroga i tuoi dati in linguaggio naturale.

> **Stato:** Beta privata — funzionante in produzione su Render + Vercel.

---

## Cosa fa

- **Dashboard** — KPI, grafici spese per categoria, trend mensile, confronto mese precedente, forecast fine mese, heatmap annuale
- **Anomaly Detection** — 5 tipi di anomalia (importo anomalo, merchant nuovo, frequenza, duplicato sospetto, orario insolito) con dettaglio statistico
- **AI Chat** — 12+ funzioni analitiche, routing deterministico + LLM, risposta in linguaggio naturale con thinking trace
- **Budget** — impostazione e monitoraggio per categoria con alert visivi (ok / warning / over)
- **Report mensile** — PDF generato automaticamente con narrativa AI e anomalie del mese
- **Export CSV** — con filtri categoria, periodo e ricerca attivi

---

## Stack tecnico

| Layer | Tecnologia |
|---|---|
| Backend | FastAPI · SQLAlchemy · SQLite (dev) |
| AI | Groq API · Llama 3.3 70B · prompt engineering custom |
| Auth | Supabase (JWT) |
| Frontend | React 19 · Vite · TypeScript |
| Stato | Zustand |
| Grafici | Recharts |
| Deploy | Render.com (backend) · Vercel (frontend) |

---

## Prerequisiti

- Python ≥ 3.11
- Node ≥ 18
- Account [Groq](https://console.groq.com) — gratuito, per la API key
- Account [Supabase](https://supabase.com) — gratuito, per l'autenticazione

---

## Avvio in 5 minuti

```bash
# 1. Clone
git clone https://github.com/Rbiagetti/Copilot-finanziario.git
cd Copilot-finanziario

# 2. Backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # compila GROQ_API_KEY e credenziali Supabase
uvicorn backend.main:app --reload
# → http://localhost:8000
# → Docs API: http://localhost:8000/docs

# 3. Frontend (nuovo terminale)
cd frontend
cp .env.example .env              # già preconfigurato per localhost
npm install && npm run dev
# → http://localhost:5173
```

---

## Variabili d'ambiente

Vedi `.env.example` (backend) e `frontend/.env.example` (frontend).
Le variabili Supabase sono le stesse per entrambi.

---

## Test

```bash
# Test deterministici — no API key richiesta
pytest backend/tests/test_ai_routing.py -v

# Backtesting conversazionale — richiede GROQ_API_KEY nel .env
pytest backend/tests/test_chat_backtest.py -v -s
# Report: backend/tests/backtest_report.html
```

---

## Reset del DB di sviluppo

```bash
rm -f data/fincopilot.db
uvicorn backend.main:app --reload   # le tabelle vengono ricreate all'avvio

# Carica 90 transazioni di test realistiche (3 mesi)
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
├── docs/                    # Documentazione tecnica
├── .env.example             # Template variabili d'ambiente backend
├── requirements.txt
└── render.yaml              # Config deploy Render.com
```

---

## Roadmap

- [x] Dashboard con AI analytics e anomaly detection
- [x] Chat AI con routing deterministico + LLM
- [x] Report mensile PDF con narrativa AI
- [x] Export CSV, budget per categoria
- [x] Backtesting conversazionale (60 test case)
- [ ] Import CSV bancario (BNCR, Fineco, N26)
- [ ] Notifiche push budget superato
- [ ] App mobile (PWA installabile)

---

## Licenza

MIT — vedi [LICENSE](LICENSE)

---

## Autore

Roberto Biagetti · [GitHub](https://github.com/Rbiagetti)
