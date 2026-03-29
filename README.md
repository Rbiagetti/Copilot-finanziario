# Copilota Finanziario

Un'applicazione avanzata per la gestione delle finanze personali, potenziata dall'Intelligenza Artificiale. Il progetto ti aiuta a monitorare le spese, gestire i budget e fornisce analisi intelligenti dei tuoi dati finanziari grazie a un assistente integrato.

## Funzionalità Principali

- **Gestione Transazioni:** Registrazione e tracciamento delle spese e delle entrate.
- **Analisi e Reportistica:** Grafici interattivi e dashboard dettagliate per comprendere al meglio i propri flussi di cassa.
- **Gestione Budget:** Impostazione di limiti di spesa e monitoraggio degli obiettivi.
- **Assistente AI (Chat):** Un copilota basato su OpenAI in grado di analizzare i dati finanziari, rispondere a domande e fornire suggerimenti personalizzati.

## Stack Tecnologico

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL gestito tramite SQLAlchemy
- **Data Analysis & Visualization:** Pandas, Matplotlib, Plotly
- **Intelligenza Artificiale:** Integrazione con OpenAI API

### Frontend
- **Framework:** React con Vite
- **Gestione Stato:** Zustand
- **Visualizzazione Dati:** Recharts
- **Icone & UI:** Lucide React
- **Auth/Backend-as-a-service:** Supabase

---

## Come Avviare il Progetto

Il progetto è diviso in due parti principali: `backend` e `frontend`. Segui questi passaggi per avviare l'ambiente di sviluppo locale.

### 1. Configurazione del Backend

Il backend è scritto in Python. Assicurati di avere Python installato e procedi come segue:

1. Naviga nella directory principale del progetto.
2. Crea e attiva l'ambiente virtuale (se non lo hai già fatto):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Su Windows usa: venv\Scripts\activate
   ```
3. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
4. Configura le variabili d'ambiente (crea un file `.env` basato sulle necessità, per DB, OpenAI, ecc.).
5. Avvia il server FastAPI:
   ```bash
   export PYTHONPATH=$PYTHONPATH:.
   uvicorn backend.main:app --reload
   ```
Il server backend sarà disponibile all'indirizzo `http://localhost:8000`. Puoi esplorare la documentazione interattiva dell'API all'indirizzo `http://localhost:8000/docs`.

### 2. Configurazione del Frontend

L'interfaccia utente è sviluppata con React.

1. Apri un nuovo terminale e naviga nella cartella `frontend`:
   ```bash
   cd frontend
   ```
2. Installa le dipendenze Node.js:
   ```bash
   npm install
   ```
3. Configura le variabili d'ambiente (crea o usa il file `.env` a partire da `.env.example`).
4. Avvia il server di sviluppo:
   ```bash
   npm run dev
   ```
L'applicazione web sarà accessibile all'indirizzo indicato dal terminale, tipicamente `http://localhost:5173`.

---

## Struttura del Progetto

- `/backend/`: Contiene il codice sorgente per le API, modelli DB e logica di business.
- `/frontend/`: Contiene il codice dell'applicazione React in Vite.
- `/data/`: File e dati usati per test o importazioni.

## Script Utili

- Per testare i dati iniziali sul base dati (seeds), puoi far riferimento a `backend/seed_test_data.py`.