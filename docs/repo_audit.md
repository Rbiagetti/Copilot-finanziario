# Repo Audit — FinCopilot
_Generato: 2026-04-27_

---

## 1. STRUTTURA ATTUALE (albero semplificato)

```
fincopilot/
├── backend/
│   ├── api/
│   │   ├── models/
│   │   │   └── schemas.py
│   │   └── routes/
│   │       ├── ai.py
│   │       ├── analytics.py
│   │       ├── budgets.py
│   │       ├── chat.py
│   │       └── transactions.py
│   ├── core/
│   │   ├── analytics/
│   │   ├── ai_engine.py
│   │   ├── auth.py
│   │   └── database.py
│   ├── tests/
│   │   ├── seed_test_data.py
│   │   ├── test_ai_routing.py
│   │   └── test_chat_backtest.py
│   ├── api/auth.py              ⚠️  duplicato di core/auth.py?
│   ├── seed_test_data.py        ⚠️  duplicato di tests/seed_test_data.py
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── Auth/LoginPage.tsx
│   │   │   ├── BudgetPanel/BudgetPanel.tsx
│   │   │   ├── ChatInterface/ChatInterface.tsx
│   │   │   ├── Dashboard/
│   │   │   │   ├── Dashboard.tsx
│   │   │   │   └── Dashboard.tsx.bak    ⚠️  da eliminare
│   │   │   ├── Layout/Sidebar.tsx
│   │   │   ├── Layout/TopBar.tsx
│   │   │   ├── Settings/SettingsPanel.tsx
│   │   │   ├── TransactionForm/TransactionForm.tsx
│   │   │   └── TransactionList/TransactionList.tsx
│   │   ├── hooks/
│   │   │   ├── useFocusTrap.ts
│   │   │   └── useTheme.ts
│   │   ├── lib/
│   │   │   └── supabase.ts
│   │   ├── store/
│   │   │   └── appStore.ts
│   │   ├── styles/
│   │   │   ├── base.css
│   │   │   ├── budget.css
│   │   │   ├── chat.css
│   │   │   ├── components.css
│   │   │   ├── dashboard.css
│   │   │   ├── layout.css
│   │   │   ├── transactions.css
│   │   │   └── utilities.css
│   │   └── utils/
│   │       ├── analyticsUtils.ts
│   │       ├── keepAlive.ts
│   │       └── voiceService.ts
│   ├── public/
│   ├── dist/                    (non tracciato in git — ok)
│   ├── .env.example
│   └── index.html
├── data/
│   └── fincopilot.db            (non tracciato — ok; .gitignore ha *.db)
├── docs/
│   ├── ai_engine.md
│   └── ai_engine_audit.md       (non tracciato — da committare o eliminare)
├── .github/
│   └── workflows/keep-alive.yml
├── .DS_Store                    ⚠️  tracciato in git — da rimuovere
├── .env                         (non tracciato — ok)
├── .gitignore
├── README.md
├── render.yaml
├── requirements.txt
└── venv/                        (non tracciato — ok)
```

---

## 2. FILE DA ELIMINARE (azione: git rm)

| Path | Motivo | Priorità |
|------|--------|----------|
| `frontend/src/components/Dashboard/Dashboard.tsx.bak` | Backup manuale, contenuto stantio, tracciato in git | **alta** |
| `.DS_Store` | File di sistema macOS, tracciato per errore in git | **alta** |
| `backend/seed_test_data.py` | Duplicato esatto di `backend/tests/seed_test_data.py`; la copia in root è tracciata e crea confusione | **alta** |

### DA VERIFICARE MANUALMENTE

| Path | Dubbio |
|------|--------|
| `backend/api/auth.py` | Stesso nome di `backend/core/auth.py` — verificare se uno è uno shim che importa l'altro o se sono due file distinti |
| `docs/ai_engine_audit.md` | Non tracciato in git; valutare se committare o rimuovere |
| `frontend/.gitignore` | Esiste un `.gitignore` nella sotto-cartella `frontend/` oltre a quello di root — verificare che non siano in conflitto |

---

## 3. FILE DA SPOSTARE O RINOMINARE

| Path attuale | Path suggerito | Motivo |
|---|---|---|
| `backend/seed_test_data.py` | **eliminare** | Copia identica già presente in `backend/tests/seed_test_data.py` |

Nessun altro file richiede spostamento: la struttura `backend/api/`, `backend/core/`, `backend/tests/` è già corretta e allineata al target.

---

## 4. .gitignore — VERIFICA E PATCH

### Stato attuale

Il `.gitignore` di root è **molto scarno** (17 righe, con `.claude/` ripetuto 3×).  
Mancano protezioni fondamentali.

### Regole mancanti da aggiungere

```gitignore
# Python — estensioni mancanti
*.pyo
*.so
build/

# DB — pattern più specifici
*.sqlite
*.sqlite3
data/*.db

# Env — varianti mancanti
.env.local
.env.*.local
.env.production

# Frontend build
frontend/dist/

# OS
.DS_Store
Thumbs.db
*.swp
*.swo

# Editor
.idea/
.vscode/settings.json
*.code-workspace

# Log e temporanei
*.log
*.bak
*.tmp
*.orig

# Test artifacts
backend/tests/backtest_report.html
```

> ⚠️  `.claude/` è scritto 3 volte nel file attuale — da deduplicare a una sola riga.  
> ⚠️  `*.png` è presente nel `.gitignore` attuale: blocca anche le immagini in `frontend/public/`. Valutare se restringere a `assets/*.png` o rimuovere se i PNG di produzione devono essere versionati.

---

## 5. STRUTTURA SUGGERITA (target)

```
fincopilot/
├── backend/                     # API FastAPI + logica di business
│   ├── api/
│   │   ├── models/              # Pydantic schemas e modelli request/response
│   │   └── routes/              # FastAPI routers (uno per dominio)
│   ├── core/                    # Logica di business: ai_engine, database, auth
│   ├── tests/                   # Tutti i test e seed (test_*, seed_*)
│   └── main.py                  # Entry point FastAPI
├── frontend/                    # React + Vite SPA
│   ├── src/
│   │   ├── api/                 # Client HTTP Axios e tipi risposta
│   │   ├── components/          # Componenti React (una cartella per componente)
│   │   ├── hooks/               # Custom hooks React
│   │   ├── lib/                 # Client di terze parti (Supabase)
│   │   ├── store/               # Zustand global store
│   │   ├── styles/              # CSS modulari per area
│   │   └── utils/               # Funzioni pure di utilità
│   ├── public/                  # Asset statici (favicon, manifest)
│   ├── .env.example             # Template variabili d'ambiente frontend
│   └── index.html
├── data/                        # Solo schema SQL o seed statici, mai *.db
├── docs/                        # Documentazione tecnica (ai_engine.md, ecc.)
├── .github/
│   └── workflows/               # CI/CD (keep-alive, futuri test automatici)
├── .env.example                 # Template variabili d'ambiente backend
├── .gitignore
├── requirements.txt
├── render.yaml                  # Config deploy Render.com
└── README.md
```

**Differenze rispetto allo stato attuale:**
- `backend/seed_test_data.py` eliminato (duplicato)
- `frontend/src/components/Dashboard/Dashboard.tsx.bak` eliminato
- `.DS_Store` rimosso dal tracking git
- `.gitignore` arricchito e deduplicato

---

## 6. README — VERIFICA ACCURATEZZA

### Errori rilevati

| Campo | README dice | Realtà (da audit strutturale) | Gravità |
|---|---|---|---|
| Database | "PostgreSQL gestito tramite SQLAlchemy" | SQLite (`data/fincopilot.db`) | **CRITICA** |
| AI provider | "Integrazione con OpenAI API" | Groq API + Llama 3.3 70B | **CRITICA** |
| Data analysis | "Pandas, Matplotlib, Plotly" | Non verificabile da struttura; potenzialmente stale | media |
| Seed script | `backend/seed_test_data.py` | Il file corretto è `backend/tests/seed_test_data.py` | media |

### Sezioni mancanti

- Variabili d'ambiente richieste (lista con valori di esempio)
- Comandi per eseguire i test
- Come resettare il DB di sviluppo
- Note su autenticazione (Supabase — non menzionato nel README)
- Stato del progetto / roadmap

---

## 7. PIANO DI AZIONE ORDINATO

### FASE 1 — Zero rischio

- [ ] Aggiorna `.gitignore`: aggiungi regole mancanti, deduplica `.claude/`
  ```bash
  # (vedi patch nella sezione 4 — applicata in automatico)
  ```
- [ ] Rimuovi `.DS_Store` dal tracking git
  ```bash
  git rm --cached .DS_Store
  ```
- [ ] Elimina `Dashboard.tsx.bak`
  ```bash
  git rm frontend/src/components/Dashboard/Dashboard.tsx.bak
  ```

### FASE 2 — Basso rischio

- [ ] Elimina `backend/seed_test_data.py` (duplicato)
  ```bash
  git rm backend/seed_test_data.py
  ```
  > Verifica prima: `diff backend/seed_test_data.py backend/tests/seed_test_data.py`  
  > Se identici → elimina. Se divergono → valuta quale è canonica.

### FASE 3 — Medio rischio (attende istruzioni)

- [ ] Riscrivi `README.md` con stack reale, env vars, comandi test
- [ ] Verifica `backend/api/auth.py` vs `backend/core/auth.py` — sono la stessa logica?
- [ ] Valuta se `*.png` nel `.gitignore` debba essere ristretto
- [ ] Decidi se committare o eliminare `docs/ai_engine_audit.md`
- [ ] Controlla che `frontend/.gitignore` non entri in conflitto con il root
