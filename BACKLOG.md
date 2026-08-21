# Backlog

## 🔐 Sicurezza — user_id nelle funzioni interne (ereditato da MULTITENANCY_STATUS.md)
Rischio attuale: LOW (protetto a livello di endpoint), ma queste funzioni interne
non filtrano ancora per user_id e vanno sistemate, specie in vista dei fix alla Chat AI:

- [ ] `chat_with_ai(question, history, user_id)` — passare user_id lungo tutta la catena
  - [ ] `interpret_question()`
  - [ ] `get_function_results()` — usa query SQL raw sulla tabella transactions, senza filtro user_id
- [ ] `execute_prebuilt_function()` — serve parametro user_id
- [ ] `build_compact_context()` — serve parametro user_id
- [ ] `get_anomalies()` / `_detect_anomalies_for_transactions()` — serve user_id (bassa priorità, vedi sotto: anomalie da rimuovere)

---

## 🏠 Dashboard / Home — semplificazione ✅ (2026-08-21)
Dopo 3 mesi d'uso reale: troppi grafici mai consultati. Sostituire con KPI card essenziali.

- [x] Rimuovere i grafici avanzati della home (mai guardati)
- [x] Rimuovere/deprioritizzare le funzioni di forecast/predict (poco utili) — rimossi Target Mese e modal Forecast
- [x] Nuova home a KPI card:
  - [x] Spese mese corrente
  - [x] Spese mese scorso
  - [x] N. transazioni mese corrente
  - [x] N. transazioni totali
  - [x] Spesa media al giorno
  - [x] Categorie del mese con relativo totale
  - [x] Fisso vs variabile (utile, mantenere)

---

## 💬 Chat AI — query basilari sulle spese ✅ (2026-08-21)
Non gestisce bene domande dirette e semplici. Niente predizioni: solo query sui dati reali.

- [x] Fix: "quanto ho speso negli ultimi 3 giorni" → non funziona (regola generica "ultimi N giorni" nel router prompt)
- [x] Fix: "quanto ho speso questo mese escludendo la categoria casa" → non funziona (param `exclude_category` su `spending_by_category`/`summary_stats`)
- [x] Verificare più in generale range di date relativi (ultimi N giorni, settimana scorsa, ecc.)
- [x] Verificare filtri per esclusione/inclusione categoria
- [x] Rimuovere la funzione anomalie dalla chat (mai utile)

Nota: probabile che il fix di questi punti richieda di risolvere anche gli item
di "Sicurezza — user_id nelle funzioni interne" sopra, dato che toccano le stesse funzioni
(`interpret_question`, `get_function_results`).
