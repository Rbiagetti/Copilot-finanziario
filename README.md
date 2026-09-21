# FinCopilot

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

**App di finanza personale con un assistente AI che risponde in italiano alle domande sulle tue spese.**

Registri le spese scrivendole o dettandole ("caffè 3 euro"), imposti dei budget per categoria, importi l'estratto conto della banca e chiedi ai tuoi dati cose come *"quanto ho speso in cibo questo mese rispetto al mese scorso?"*, ottenendo risposta, tabella e grafico.

**Demo live:** [copilot-finanziario-ten.vercel.app](https://copilot-finanziario-ten.vercel.app) (registrazione con email o Google; il backend gratuito su Render può impiegare qualche secondo a svegliarsi)

![Dashboard](docs/screenshots/dashboard.png)

> Gli screenshot usano dati di esempio generati per la demo, non dati reali.

---

## Funzionalità

### Dashboard
KPI essenziali (spesa del mese corrente e precedente, numero di transazioni, spesa media giornaliera), ripartizione per categoria e andamento di costi fissi e variabili.

### Chat AI
Domande in linguaggio naturale sulle proprie spese. Il modello non scrive SQL libero: sceglie una tra le funzioni analitiche predefinite (spese per categoria, confronto tra mesi, trend, top transazioni, abbonamenti, stato dei budget, what-if...), che viene eseguita sul database dell'utente. Il risultato viene poi commentato in italiano, con tabella, grafico e domande di approfondimento.

![Chat AI](docs/screenshots/chat.png)

### Transazioni
Inserimento da testo o voce, con parsing automatico di importo e categoria, oppure manuale. Ricerca, filtri per categoria e periodo, marcatura delle spese ricorrenti, eliminazione multipla ed export CSV.

![Transazioni](docs/screenshots/transazioni.png)

### Budget
Un budget mensile per categoria, con stato a tre livelli: ok, in avvicinamento, sforato.

![Budget](docs/screenshots/budget.png)

### Mobile
L'interfaccia è pensata anche per il telefono: barra di navigazione in basso, layout a colonna singola, installabile come PWA.

<p align="center">
  <img src="docs/screenshots/mobile-dashboard.png" alt="Dashboard su mobile" width="23%">
  <img src="docs/screenshots/mobile-chat.png" alt="Chat AI su mobile" width="23%">
  <img src="docs/screenshots/mobile-transazioni.png" alt="Transazioni su mobile" width="23%">
  <img src="docs/screenshots/mobile-budget.png" alt="Budget su mobile" width="23%">
</p>

### Import da estratto conto
Caricamento di file CSV, Excel o PDF. L'app riconosce le colonne (euristica più AI), mostra un'anteprima che l'utente può correggere, evita i duplicati rispetto alle transazioni già presenti e categorizza automaticamente le righe che ne sono prive.

### Altro
Report mensile in PDF con commento generato dall'AI, categorie personalizzate, scelta del modello AI per utente, login con email o Google, tema scuro, installabile come PWA.

---

## Architettura

```
 React (Vite, Zustand, Recharts)          Vercel
        │  JWT Supabase
        ▼
 FastAPI + SQLAlchemy                     Render
   ├─ auth middleware (verifica JWT)
   ├─ motore AI (router → funzione → interpretazione)  ──►  Groq API (Qwen)
   └─ import engine (CSV / XLSX / PDF)
        │
        ▼
 PostgreSQL + Auth                        Supabase   (SQLite in sviluppo)
```

Scelte principali:

- **Multi-tenancy:** ogni tabella ha una colonna `user_id` (UUID Supabase) e ogni endpoint filtra per utente. Lo schema è versionato con Alembic.
- **Chat AI con funzioni predefinite:** l'LLM sceglie la funzione e ne interpreta il risultato, ma non genera query. I parametri restituiti dal router vengono validati e limitati a intervalli sicuri, quindi un output malformato del modello non può produrre query arbitrarie. Le domande fuori tema sono intercettate da un pre-filtro senza chiamare l'LLM.
- **Determinismo:** temperatura 0 e seed fisso sul router, output JSON forzato, limiti rigidi su lunghezza input, cronologia, righe e punti dei grafici.
- **Import senza stato lato server:** `/import/preview` e `/import/commit` ricevono entrambe il file, così non serve conservare nulla tra le due chiamate.

---

## Stack

| Layer | Tecnologie |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic, pandas, pdfplumber, ReportLab |
| AI | Groq API (modelli Qwen) tramite client OpenAI-compatibile |
| Database e auth | Supabase (PostgreSQL + Auth), SQLite in locale |
| Frontend | React 19, TypeScript, Vite, Zustand, Recharts, React Router |
| Deploy | Render (API), Vercel (frontend), GitHub Actions (health check) |

---

## Avvio in locale

Servono Python ≥ 3.11, Node ≥ 18, una [API key Groq](https://console.groq.com) e un progetto [Supabase](https://supabase.com), entrambi gratuiti.

```bash
git clone https://github.com/Rbiagetti/Copilot-finanziario.git
cd Copilot-finanziario

# Backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # inserisci GROQ_API_KEY e credenziali Supabase
uvicorn backend.main:app --reload
# API:  http://localhost:8000    Docs: http://localhost:8000/docs

# Frontend (in un altro terminale)
cd frontend
cp .env.example .env
npm install && npm run dev
# App:  http://localhost:5173
```

Le variabili d'ambiente sono descritte in `.env.example` (backend) e `frontend/.env.example` (frontend).

**Dati di esempio.** Con `SUPABASE_URL` vuoto il backend salta l'autenticazione e usa un utente di sviluppo. In quella modalità puoi caricare 90 transazioni realistiche con:

```bash
python -m backend.tests.seed_test_data
```

---

## Test

```bash
# Test deterministici: routing AI, validazione, import (nessuna API key richiesta)
pytest backend/tests/test_ai_routing.py backend/tests/test_import_engine.py -v

# Backtest conversazionale della chat: richiede GROQ_API_KEY
pytest backend/tests/test_chat_backtest.py -v -s
```

---

## Struttura del progetto

```
├── backend/
│   ├── api/
│   │   ├── models/          # schemi Pydantic
│   │   └── routes/          # router FastAPI (chat, transazioni, budget, import, report...)
│   ├── core/
│   │   ├── ai_engine.py     # router, funzioni analitiche, guardrail
│   │   ├── import_engine.py # parsing CSV / XLSX / PDF e mapping colonne
│   │   └── database.py      # modelli SQLAlchemy
│   ├── tests/
│   └── main.py
├── frontend/src/
│   ├── components/          # una cartella per area (Dashboard, Chat, Budget...)
│   ├── store/               # stato globale (Zustand)
│   ├── styles/              # CSS modulare
│   └── api/                 # client HTTP
├── alembic/                 # migrazioni
├── docs/screenshots/
└── render.yaml              # configurazione deploy Render
```

---

## Roadmap

- [x] Chat AI con funzioni analitiche predefinite
- [x] Budget per categoria
- [x] Report mensile in PDF
- [x] Import da estratto conto (CSV, Excel, PDF)
- [x] Multi-utente con Supabase Auth
- [x] PWA installabile
- [ ] Notifiche quando un budget viene superato
- [ ] Import con formati specifici per le principali banche italiane

---

## Licenza

MIT, vedi [LICENSE](LICENSE).

## Autore

Roberto Biagetti · [GitHub](https://github.com/Rbiagetti)
