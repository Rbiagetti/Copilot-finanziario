# Backlog — FinCopilot

Ultimo aggiornamento: **2026-11-02**

Documento operativo unico. Ripristinato dalla storia git (`b0fd7b5^`) e integrato con
il backlog esteso prodotto dalla sessione Expert Team / AI Cofounder, più il lavoro
svolto tra agosto e settembre 2026.

Legenda: ✅ fatto · ⏳ aperto · 🟡 parziale · ❌ scartato
Priorità: 🔴 alta · 🟡 media · 🟢 bassa

**Regola:** un task per sessione/commit. Aggiornare questo file quando un task viene
chiuso, indicando commit e gap residui. Il contesto tecnico è in `AGENTS.md`.

---

## 🔐 Sicurezza — `user_id` nelle funzioni interne ✅

Rischio storico: le funzioni interne del motore chat non filtravano per utente
(protezione solo a livello di endpoint).

- [x] `chat_with_ai(question, history, user_id)` — `user_id` passato lungo tutta la catena
- [x] `interpret_question()` / `get_function_results()`
- [x] `execute_prebuilt_function()` — `user_id` obbligatorio
- [x] `build_compact_context()` / `build_context()` — `user_id`
- [x] Rimozione completa della rilevazione anomalie (non più usata in UI)

Chiuso il **2026-09-22**, commit `f472256`. Verificato con due utenti di test e dati
distinti: nessuna funzione restituisce più dati dell'altro utente.

> Nota: la chat AI era la falla più grave rimasta dopo il fix RLS su Supabase.
> Se si aggiunge una nuova `_fn_*`, il filtro `user_id` è obbligatorio.

---

## 🏠 Dashboard / Home — semplificazione ✅ (2026-08-21)

Dopo mesi d'uso reale: troppi grafici mai consultati. Sostituiti con KPI essenziali.

- [x] Rimossi i grafici avanzati della home
- [x] Rimossi forecast/predict (Target Mese, modal Forecast)
- [x] Home a KPI card: spese mese corrente, spese mese scorso, n. transazioni mese,
      n. transazioni totali, spesa media al giorno, categorie del mese
- [x] Fisso vs variabile mantenuto
- [x] Aggiunta "spesa totale" tra i KPI (6 card, layout mobile migliore)

---

## 💬 Chat AI — query basilari sulle spese ✅ (2026-08-21)

- [x] "quanto ho speso negli ultimi 3 giorni" → regola generica "ultimi N giorni"
- [x] "quanto ho speso questo mese escludendo la categoria casa" → parametro
      `exclude_category` su `query_spending`
- [x] Range di date relativi (ultimi N giorni, settimana scorsa, ...)
- [x] Filtri per inclusione/esclusione categoria
- [x] Esclusione delle transazioni **future** dai calcoli (bug grave: una spesa tra
      due settimane finiva in "ultimi 3 giorni" e in "questo mese")
- [x] Consolidamento delle ~20 funzioni: 6 funzioni di aggregazione fuse in
      `query_spending` (query builder parametrico, non SQL libero)
- [x] Router multi-funzione: il LLM decide 1..N funzioni, i `MACRO_INTENTS`
      keyword-based sono stati rimossi
- [x] Thinking flow visibile in chat, poi ridisegnato in stile professionale
- [x] Markdown-lite nelle risposte (liste, paragrafi, tabelle) + renderer frontend
- [x] Slider temporale nei filtri transazioni (da primo mese a mese corrente)
- [x] Filtro categorie con dropdown

---

## 🗂️ EPIC A — Import estratti conto

✅ **Implementata (2026-08-22)**, commit `4e4f9f1`, in produzione.
Sezione "AI Importer" in Impostazioni: upload CSV/XLSX/PDF → mapping colonne
(euristica + AI, editabile) → preview → conferma → dedup + categorizzazione AI + import.
Verificata end-to-end su PDF reale Buddybank/UniCredit (72 spese, dedup corretto).

**Fix critici post-lancio (2026-08-22, commit `aa6b379`)**: due bug sulle date che
corrompevano i dati in silenzio — (1) date ISO scambiate mese/giorno da
`dateutil` con `dayfirst=True`, (2) mesi italiani abbreviati non riconosciuti, con
data inventata. Corretti con parsing ISO esplicito + mappa mesi italiani. Aggiunto
supporto CSV con preambolo (formato Revolut "consolidated statement"). 19 test di
regressione in `test_import_engine.py`.

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| T-001 | Parser CSV multi-formato (N26, Revolut, Fineco, Unicredit, generico): encoding, separatore, date | 🔴 | L | ✅ |
| T-002 | Deduplication per (date, amount, description) con conteggio nel response | 🔴 | S | ✅ |
| T-003 | Categorizzazione AI in batch (30 descrizioni per chiamata) | 🔴 | M | ✅ |
| T-004 | UI preview import con mapping colonne suggerito dall'AI e editabile | 🔴 | L | ✅ |
| T-005 | UI conferma + **override categoria riga per riga** prima del commit | 🔴 | M | 🟡 |
| T-006 | Feedback post-import (imported / skipped / da verificare) | 🟡 | S | ✅ |
| T-007 | Test parser su export reali N26, Revolut, Fineco, UniCredit | 🔴 | M | 🟡 |
| T-021 | Rate limiting import: max 5 MB, max 1000 righe, max 3 import/giorno | 🔴 | S | 🟡 |
| T-023 | Supporto XLS/XLSX (openpyxl/pandas) nella stessa pipeline | 🔴 | M | ✅ |
| T-024 | Supporto PDF via `pdfplumber` (banche senza export CSV, es. Buddybank) | 🔴 | M | ✅ |

**Gap residui Epic A**

- **T-005**: manca l'override manuale della categoria per singola riga. Se il file
  non ha una colonna categoria, tutte le righe passano dalla categorizzazione AI in
  batch senza possibilità di correzione puntuale.
- **T-007**: testato su CSV sintetico, PDF UniCredit/Buddybank e CSV Revolut
  "consolidated statement". Mancano export reali **N26** e **Fineco**.
- **T-021**: limiti per singola richiesta presenti in `import_engine.py`
  (5 MB / 1000 righe). Manca il limite giornaliero per utente.

**Percorso critico residuo:** T-005 → T-007 → T-021 (≈ 0,5–1 giorno).

---

## 🗂️ EPIC B — Feature comportamentali AI (differenzianti post-lancio)

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| T-008 | "Confessionale": quando l'utente inserisce una spesa in chat, il copilota risponde con contesto reale (vs media, vs mese scorso) | 🟡 | S | ⏳ |
| T-009 | "Specchio del futuro" nel briefing: forecast in ore di lavoro equivalenti + proiezione annuale | 🟡 | M | ⏳ |
| T-010 | Schema DB `goals` + `goal_progress` | 🟡 | S | ⏳ |
| T-011 | API goals CRUD + endpoint progress | 🟡 | M | ⏳ |
| T-012 | AI Challenger: categoria con più varianza negli ultimi 30 gg, sfida −20% vs media su 7 gg (min 14 gg di dati) | 🟡 | M | ⏳ |
| T-013 | UI AI Challenger: card in dashboard, progress bar, accept/decline, celebrazione | 🟡 | L | ⏳ |
| T-014 | UI Goals: sezione "I miei obiettivi", form categoria + target + data | 🟡 | M | ⏳ |
| T-015 | Notifica proattiva goals: alert nel briefing se >70% del budget a metà mese | 🟡 | S | ⏳ |

**Stima Epic B:** ~5 giorni.

---

## 🗂️ EPIC C — Weekly Digest AI (nice-to-have)

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| T-016 | Endpoint weekly digest: spesa settimana, categoria sorpresa, domanda riflessiva AI | 🟢 | M | ⏳ |
| T-017 | UI card digest collassabile in dashboard, ogni lunedì | 🟢 | S | ⏳ |
| T-018 | Scheduling digest (APScheduler settimanale, tabella `digests`) | 🟢 | M | ⏳ |

**Stima Epic C:** ~1 giorno.

---

## 🗂️ EPIC D — Quality & Onboarding

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| T-019 | Onboarding 3 step al primo accesso: prima spesa NL, import CSV, prima domanda al copilota | 🟡 | M | ⏳ |
| T-020 | Stato "dati insufficienti" con CTA quando ci sono meno di 5 transazioni | 🟡 | S | ⏳ |
| T-021 | Rate limiting import (vedi Epic A) | 🔴 | S | 🟡 |
| T-022 | Error tracking import: log strutturato degli errori di parsing | 🟡 | S | ⏳ |

**Stima Epic D:** ~1–2 giorni.

---

## 🗂️ EPIC E — Gap funzionali basilari

Audit leggero (2026-08-24/25) su cosa manca rispetto a un'app di gestione spese
"basilare".

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| G-01 | ~~Toggle tema chiaro/scuro~~ | — | — | ❌ scartato (predisposizione rimossa) |
| G-02 | Categorie personalizzate (CRUD in Impostazioni, soft-delete, integrate in transazioni/budget/importer/quick-add) | 🟡 | M | ✅ `429d7c7` |
| G-03 | Filtro per importo (min/max) in Transazioni | 🟢 | S | ⏳ |
| G-04 | Allegato/foto scontrino sulla transazione | 🟡 | M | ⏳ |
| G-05 | Conti multipli: UI reale sul campo `account` già in DB (oggi non usato) | 🟡 | M | ⏳ |
| G-06 | Notifica proattiva (email/push) per budget/anomalie, non solo on-demand | 🟡 | M/L | ⏳ |
| G-07 | Ricorrenza automatica (generazione mensile reale, non solo flag manuale) | 🟡 | L | ⏳ |
| G-08 | Tracking entrate (`type: income/expense`) — richiede decisione di prodotto | 🔴 se voluta | XL | ⏳ |
| G-09 | Export/backup completo JSON (transazioni + categorie + budget) | 🟢 | S/M | ⏳ |
| G-10 | Multi-valuta | 🟢 | L | ⏳ |

**✅ Categorie allineate (2026-11-02).** Fonte unica in `backend/core/categories.py`
(11 standard, incluso `intrattenimento`); `schemas.py` e `ai_engine.py` importano da lì.
Il router della chat carica le categorie attive dell'utente (standard + personalizzate)
a inizio richiesta e le passa al prompt e a un `ContextVar` per-request: chiedere
"quanto ho speso in palestra?" ora filtra davvero la categoria personalizzata.
5 test di regressione in `test_ai_routing.py`.

---

## 🗂️ EPIC F — Wealth Monitor (patrimonio a snapshot)

✅ **v1 implementata (2026-11-02)**. Sezione "Patrimonio" in sidebar (`/wealth`):
conti configurabili dall'utente, foto periodiche dei saldi, andamento, composizione
per tipo di conto. Solo attività (nessuna passività), come deciso in fase di spec.

| ID | Titolo | Priorità | Stima | Status |
|---|---|---|---|---|
| W-01 | Conti configurabili: nome libero + tipo (liquidità/investimenti/previdenza/immobili/altro), rinomina, archiviazione soft | 🔴 | S | ✅ |
| W-02 | Snapshot per data con upsert `(account_id, snapshot_date)`, prefill dall'ultimo saldo ≤ data | 🔴 | M | ✅ |
| W-03 | Overview: serie storica, variazione €/%, composizione per tipo, saldo e delta per conto | 🔴 | M | ✅ |
| W-04 | UI: KPI, line chart, form "Aggiorna saldi", gestione conti, layout mobile | 🔴 | M | ✅ |
| W-05 | Test deterministici: CRUD, upsert, overview, isolamento utenti, validazioni | 🔴 | S | ✅ |
| W-06 | Integrazione chat AI ("quanto è cresciuto il mio patrimonio?") | 🟡 | M | ⏳ |
| W-07 | Passività / patrimonio netto (conti di tipo debito sottratti dal totale) | 🟡 | S | ⏳ |
| W-08 | Import automatico saldi o sync bancaria | 🟢 | L | ⏳ |
| W-09 | Ripristino di un conto archiviato (oggi lo storico resta in DB ma non è più visibile) | 🟢 | S | ⏳ |

**Note di design**

- `DELETE /wealth/accounts/{id}` è un soft delete: il conto sparisce da form, totali
  e composizione, ma gli snapshot restano in DB (base per W-09).
- La data della foto non può essere futura (stessa guardia del parser import).
- Il salvataggio è idempotente: rifare la stessa data aggiorna i valori, non duplica.
- La serie storica considera solo i conti attivi; archiviare un conto ne rimuove
  anche i valori passati dalla vista (comportamento voluto: "chiuso, non lo conto più").

---

## ✅ Completato fuori backlog

### 2026-11-02

- **Categorie**: fonte unica in `backend/core/categories.py`, `intrattenimento`
  standard ovunque, chat AI abilitata alle categorie personalizzate per utente.
- **Fix mobile**: campi di modifica conto e campo data del patrimonio allineati
  agli altri frame su iOS (zoom Safari e min-width del date picker).

### 2026-05-04

- **Multi-tenancy**: `user_id` su tutte le tabelle, endpoint filtrati, migrazione
  Alembic, logout che pulisce la cache frontend
- **Anomalie AI on-demand**: cache per utente, 5 tipi di anomalia, refresh manuale
  *(poi rimosse dall'UI il 2026-09-21)*
- **Report PDF mensile**: narrativa AI + grafici + anomalie
- **Fix voce**: le transazioni da linguaggio naturale salvano `user_id`

### 2026-08-21 → 08-25

- Redesign completo del motore chat: router multi-funzione, determinismo, bound,
  `query_spending` unificata, what-if deterministico
- Backtesting end-to-end: seed 90 transazioni, 60 casi conversazionali, report HTML
- Thinking flow in chat + redesign professionale
- Audit strutturale repo, `.gitignore`, pulizia file generati, README aggiornato
- Export CSV transazioni con auth Bearer e Blob download
- Rimozione del drilldown dal pie chart della dashboard
- Slider temporale e filtri categoria nelle transazioni
- Categorie personalizzate (G-02)

### 2026-09-09 → 09-22

- **RLS Supabase** verificata e corretta (tabelle pubbliche non leggibili con anon key)
- **Isolamento chat per utente** — commit `f472256` (vedi sezione Sicurezza)
- Fix "sessione scaduta" e gestione token frontend
- Privacy Policy e Termini di servizio
- SEO: meta description, favicon, URL icone versionati
- README portfolio con screenshot desktop/mobile, registro formale, diagrammi ASCII
- Rimozione della rilevazione anomalie dall'interfaccia — commit `d18ac71`
- Selettore modello AI per utente + fix model ID Groq
- Redesign frontend stile "Second Brain" (nero, Geist Mono, dot grid, angoli squadrati)
- Fix mobile: barra navigazione iOS, safe area, tabelle chat, grafici non interattivi
  al tocco per non bloccare lo scroll

---

## 🧭 Prossimi passi suggeriti

In ordine di rapporto valore/rischio:

1. **T-005 + T-007 + T-021** — chiudere l'Epic A (import affidabile su banche reali).
2. **T-019 + T-020** — onboarding e stato "dati insufficienti": riducono l'abbandono
   al primo accesso.
3. **G-03 + G-09** — quick win su transazioni (filtro importo, backup JSON).
4. **T-008 + T-012** — prime feature comportamentali AI, il vero differenziatore.
5. **G-05 / G-08** — richiedono decisione di prodotto prima di essere stimate.

**Debito tecnico noto**

- `ai_engine.py` è un monolite da 2.237 righe: ogni nuova funzione aumenta il rischio
  di regressione. Se si tocca pesantemente, valutare estrazione in moduli
  (`router.py`, `functions/`, `interpret.py`) con test a copertura invariata.
- Categorie duplicate tra `schemas.py` e `ai_engine.py` (10 vs 11).
- `backend/core/auth.py` e `backend/api/auth.py` contengono logica JWT duplicata.
- `rate_limit.py` rimosso ma restano i `.pyc`: pulire `__pycache__` quando si tocca
  l'area import.
