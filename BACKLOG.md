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

## 🏠 Dashboard / Home — semplificazione
Dopo 3 mesi d'uso reale: troppi grafici mai consultati. Sostituire con KPI card essenziali.

- [ ] Rimuovere i grafici avanzati della home (mai guardati)
- [ ] Rimuovere/deprioritizzare le funzioni di forecast/predict (poco utili)
- [ ] Nuova home a KPI card:
  - [ ] Spese mese corrente
  - [ ] Spese mese scorso
  - [ ] N. transazioni mese corrente
  - [ ] N. transazioni totali
  - [ ] Spesa media al giorno
  - [ ] Categorie del mese con relativo totale
  - [ ] Fisso vs variabile (utile, mantenere)

---

## 💬 Chat AI — query basilari sulle spese
Non gestisce bene domande dirette e semplici. Niente predizioni: solo query sui dati reali.

- [ ] Fix: "quanto ho speso negli ultimi 3 giorni" → non funziona
- [ ] Fix: "quanto ho speso questo mese escludendo la categoria casa" → non funziona
- [ ] Verificare più in generale range di date relativi (ultimi N giorni, settimana scorsa, ecc.)
- [ ] Verificare filtri per esclusione/inclusione categoria
- [ ] Rimuovere la funzione anomalie dalla chat (mai utile)

Nota: probabile che il fix di questi punti richieda di risolvere anche gli item
di "Sicurezza — user_id nelle funzioni interne" sopra, dato che toccano le stesse funzioni
(`interpret_question`, `get_function_results`).
