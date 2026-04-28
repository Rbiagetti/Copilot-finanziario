# Audit Anomalie — FinCopilot (RISOLTO ✅)

Questo documento analizza lo stato attuale del sistema di rilevamento e visualizzazione delle anomalie, identificando le incoerenze tra backend e frontend e proponendo un piano di fix per rendere "Anomalies" una fonte di verità unica.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FASE 0 — AUDIT VELOCE: IDENTIFICARE I DANNI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## SEZIONE 1: SHAPE ANOMALIA

**1a) Return type di `get_anomalies()` (backend/core/ai_engine.py)**
Ritorna una `list` di oggetti (max 20). Ogni oggetto ha questa struttura:
```python
{
    "id": int,
    "amount": float,
    "category": string,
    "description": string,
    "date": string,
    "time": string | None,
    "z_score": float,
    "avg_category": float,
    "pct_above_avg": int,
    "detection_type": string,  # "amount_spike", "new_merchant", etc.
    "detection_label": string,
    "severity": string,        # "high", "medium", "low"
    "stats": dict              # Struttura variabile per tipo
}
```

**1b) Incoerenza tra i caricamenti**
- **Dashboard (`GET /ai/anomalies`)**: Usa `get_anomalies_for_month()`. Ritorna un `dict` con `{"anomalies": [], "count": N, "by_type": {}, "generated_at": ISO}`.
- **Report (`GET /report/monthly`)**: Usa `get_anomalies()` (che guarda gli ultimi 60 giorni indipendentemente dal mese del report!) e poi filtra in memoria. **BUG CRITICO**: Se genero un report di 6 mesi fa, le anomalie saranno vuote perché `get_anomalies()` non le trova.
- **Refresh (`POST /ai/anomalies/refresh`)**: Usa `get_anomalies_for_month()` con `force_refresh=True`. Coerente con la Dashboard.

**1c) Campi Obbligatori vs Opzionali**
- **Obbligatori**: `id`, `amount`, `category`, `date`, `detection_type`, `detection_label`, `severity`.
- **Opzionali (o variano)**: `time`, `stats` (cambia schema), `z_score`, `avg_category`, `pct_above_avg` (spesso settati a 0 per detector non statistici).

---

## SEZIONE 2: ANOMALY DETECTION LOGIC

**2a) Detector esistenti**
1. `amount_spike`: Z-score su base categoria (ultimi 60gg).
2. `new_merchant`: Prima volta che compare una descrizione (sopra €10).
3. `frequency_spike`: Troppe transazioni in una categoria nell'ultima settimana vs media 60gg.
4. `duplicate_suspect`: Transazioni identiche entro 48 ore.
5. `unusual_time`: Transazione fuori dall'orario abituale (percentile 10-90) della categoria.

**2b) Anomalie "parziali"**
Sì, `new_merchant`, `frequency_spike`, `duplicate_suspect` e `unusual_time` settano `z_score: 0.0`, `avg_category: 0.0` e `pct_above_avg: 0`. Questo è un "residuo" del vecchio sistema basato solo su `amount_spike`.

**2c) Aggregazione finale**
In `get_anomalies()` e `_detect_anomalies_for_transactions()`:
- Ordina per date (DESC), poi per severity (High → Low).
- Cap a 20 anomalie.
- **PROBLEMA**: La deduplicazione non è esplicita se un detector "overlap" con un altro (es: un amount spike che è anche un new merchant).

---

## SEZIONE 3: CACHE BACKEND

**3a) Cache in-memory**
Esiste `_anomaly_cache` in `backend/core/ai_engine.py`.
- **Chiave**: `(year, month)` per ogni `user_id`.
- **Scrittura**: `get_anomalies_for_month()` scrive dopo il calcolo.
- **Invalidazione**: `invalidate_anomaly_cache()` (per utente o per mese specifico).
- **BUG**: Non viene mai chiamata l'invalidazione quando si crea/modifica una transazione! La cache rimane "stale" fino a riavvio server o click su "Refresh".

**3b) Performance**
Se la cache missa, ricalcola tutto (5 detector). Per il report, questo viene fatto on-demand se si usa l'endpoint POST.

**3c) Coerenza behavior**
- `GET /ai/anomalies`: Usa cache.
- `POST /ai/anomalies/refresh`: Invalida e ricalcola.
- `GET /report/monthly`: **FALLISCE** (usa `get_anomalies()` invece della cache per mese).
- `POST /report/monthly/generate`: Usa `get_anomalies_for_month()`. Ok.

---

## SEZIONE 4: FRONTEND STATE

**4a) appStore.ts**
Lo store `anomalies` ha: `data`, `count`, `by_type`, `generated_at`, `has_new_transactions`.
- **Incoerenza**: Il backend ritorna già `count` e `by_type`, ma lo store li ricalcola in `setAnomalies`. Inutile.

**4b) Trigger di setting**
- Mount Dashboard: Sì (`loadAnomalies`).
- Dopo Refresh: Sì.
- Dopo caricamento report: **NO**. Il report scarica il file ma non aggiorna lo store globale se ha ricalcolato le anomalie.

**4c) Resettaggio `has_new_transactions`**
Viene resettato solo quando `setAnomalies` viene chiamato con successo. Se l'utente chiude la tab o naviga, rimane `true`.

---

## SEZIONE 5: FRONTEND → BACKEND FLOW

**5a) Dashboard mount**
Chiama `getAnomalies()`. Non passa parametri. Il backend assume "mese corrente".
- **LIMITE**: Se navigo la dashboard nel passato, le anomalie non cambiano (mostrano sempre il mese corrente).

**5b) Refresh**
Chiama `refreshAnomalies()` (POST). Ricalcola il mese corrente.

**5c) Report**
Chiama `generateMonthlyReportWithAnomalies(year, month)` (POST).
- Questo ricalcola le anomalie per il mese specifico se non in cache.
- **PROBLEMA**: Se le anomalie cambiano durante la generazione del report, la Dashboard (se aperta su quel mese) non lo sa finché non fa refresh.

---

## SEZIONE 6: ORCHESTRAZIONE E BOTTLENECK

**6a) Scenario: Genera Report**
Il report attende il calcolo delle anomalie (sequenziale). L'utente vede "Preparazione anomalie..." poi "Generazione PDF...". Corretto, ma se il calcolo fallisce, l'intero report fallisce.

**6b) Scenario: TX mentre generi**
La TX salva a DB. Il report che sta girando potrebbe leggere dati parziali o la cache vecchia se non è stata invalidata.

---

## SEZIONE 7: COERENZA DASHBOARD ↔ REPORT

**7a) Stesso numero?**
No, perché il report usa `[:5]` (max 5) mentre la dashboard ne mostra fino a 20.

**7b) Labeling**
Le label sono costruite nel backend, quindi coerenti.

**7c) Severity**
Il report non usa colori per la severity delle anomalie (solo tabella testo), mentre la dashboard usa icone/colori.

---

## SEZIONE 8: PROBLEMI RISOLTI ✅

1. **RISOLTO** — **Report GET /monthly buggato**: Ora usa `get_anomalies_for_month(year, month)` garantendo coerenza con i dati storici.
2. **RISOLTO** — **Cache Invalidation mancante**: Aggiunta chiamata `invalidate_anomaly_cache` in tutti gli endpoint di scrittura transazioni (POST, PUT, DELETE, PARSE).
3. **RISOLTO** — **Incoerenza Shape**: `get_anomalies_for_month` è ora l'unico entry point centralizzato con risposta standardizzata.
4. **RISOLTO** — **Ricalcolo inutile in Frontend**: Lo store Zustand ora accetta la risposta completa del backend senza ricalcoli ridondanti.
5. **RISOLTO** — **Deduplicazione**: Implementata logica di deduplicazione nel backend per evitare che la stessa transazione compaia più volte se triggera più detector.
6. **RISOLTO** — **Feedback caricamento**: Implementato `loading` state globale nello store delle anomalie, usato dalla Dashboard per feedback immediato.

---

# STATO FINALE
Il sistema è ora robusto, coerente e performante. La cache garantisce risposte rapide e l'invalidazione automatica assicura che l'utente veda sempre dati aggiornati dopo una modifica.
