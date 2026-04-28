# AI Engine Audit — FinCopilot

Audit read-only eseguito il 2026-04-26. Zero modifiche al codice.
Fonti: `backend/core/ai_engine.py`, `backend/api/routes/chat.py`, `backend/api/models/schemas.py`, `frontend/src/components/ChatInterface/ChatInterface.tsx`, `frontend/src/api/client.ts`.

---

## 1. FLUSSO ATTUALE

```
FRONTEND (ChatInterface.tsx:212-213)
  │
  │  history = messages.map(m => ({role, content}))  ← tutti i messaggi in memoria locale
  │  sendChat(msg, history)  → POST /api/v1/chat/
  │
  ▼
BACKEND (chat.py:13-37)
  │
  │  ChatRequest { message: str, history: List[Dict] }  (schema validato da Pydantic)
  │  chat_with_ai(request.message, request.history)
  │
  ▼
ai_engine.py:chat_with_ai() (riga 646)
  │
  ├─[1a] _select_function(question, history)  ← LLM CALL #1
  │       model=llama-3.3-70b-versatile, temperature=0, max_tokens=200
  │       Restituisce: { use_function, in_perimeter }
  │
  ├─ BRANCH A — in_perimeter=False  (domanda fuori perimetro)
  │       └─ Ritorna _OUT_OF_SCOPE statico (nessuna LLM call aggiuntiva)
  │          TOTALE CHIAMATE LLM: 1
  │
  ├─ BRANCH B — in_perimeter=True + use_function!=null  (funzione preconfezionata)
  │       ├─[2b] execute_prebuilt_function(name, params)  ← SOLO SQL, nessuna LLM call
  │       │       Esegue query DB deterministica
  │       ├─[3b] _format_data_for_interpretation(chart_data, table_data)  ← stringa testo
  │       └─[4b] _interpret_results(question, data_summary)  ← LLM CALL #2
  │               model=llama-3.3-70b-versatile, temperature=0.3, max_tokens=500
  │               Restituisce: { answer, followup_questions }
  │          TOTALE CHIAMATE LLM: 2
  │
  └─ BRANCH C — in_perimeter=True + use_function=null  (testo finanziario, no funzione)
          ├─[2c] build_compact_context()  ← SOLO SQL, nessuna LLM call
          └─[3c] _answer_in_perimeter(question, compact_ctx)  ← LLM CALL #2
                  model=llama-3.3-70b-versatile, temperature=0.3, max_tokens=400
                  Restituisce: { answer, followup_questions }
             TOTALE CHIAMATE LLM: 2

BACKEND (chat.py:21-29)
  │  Salva in ChatHistory (role=user + role=assistant)
  │  Ritorna ChatResponse { answer, chart_data, data_table, followup_questions }
  │
  ▼
FRONTEND (ChatInterface.tsx:215-225)
  Appende messaggio assistant a messages[]
  Renderizza testo + grafico (se chart_data) + tabella (se data_table) + followup buttons
```

---

## 2. CATALOGO FUNZIONI

| Nome funzione | Parametri | SQL grezza (dal codice) | Tipo output | Max righe restituite |
|---|---|---|---|---|
| `_q` (ai_engine.py:21) | `sql: str, params: dict=None` | generica — esegue qualsiasi SQL passato | `list[Row]` | `fetchall()` — illimitato |
| `_scalar` (ai_engine.py:27) | `sql: str, params: dict=None` | generica — esegue qualsiasi SQL passato | `Any` (primo valore prima riga) | 1 |
| `build_context` (ai_engine.py:47) | nessuno | `SELECT COUNT(*) FROM transactions` / `SELECT MIN(date), MAX(date) FROM transactions` / `SELECT SUM(amount) FROM transactions` / `SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d` / `SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30` / `SELECT category, COUNT(*), SUM(amount), AVG(amount) FROM transactions WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC` | `str` (contesto formattato) | illimitato per categorie (nessun LIMIT) |
| `build_compact_context` (ai_engine.py:450) | nessuno | `SELECT SUM(amount), COUNT(*) FROM transactions WHERE date >= :d` / `SELECT SUM(amount) FROM transactions WHERE date >= :d60 AND date < :d30` / `SELECT category, SUM(amount) FROM transactions WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC LIMIT 5` | `str` | 5 (LIMIT 5 sulle categorie) |
| `_fn_spending_by_category` (ai_engine.py:133) | `db_path: str, params: dict` | `SELECT category, SUM(amount) FROM transactions WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC` | `dict {chart_data, table_data}` | illimitato (nessun LIMIT) |
| `_fn_daily_trend` (ai_engine.py:149) | `db_path: str, params: dict` | `SELECT date, SUM(amount) FROM transactions WHERE date >= :d GROUP BY date ORDER BY date` | `dict {chart_data, table_data}` | illimitato (nessun LIMIT) |
| `_fn_top_transactions` (ai_engine.py:164) | `db_path: str, params: dict` | `SELECT date, category, description, amount FROM transactions WHERE date >= :d [AND category = :cat] ORDER BY amount DESC LIMIT :n` | `dict {chart_data, table_data}` | `n` (default 10) |
| `_fn_month_vs_month` (ai_engine.py:190) | `db_path: str, params: dict` | `SELECT category, SUM(CASE WHEN date >= :ms THEN amount ELSE 0 END) as curr, SUM(CASE WHEN date >= :pms AND date < :ms THEN amount ELSE 0 END) as prev FROM transactions WHERE date >= :pms GROUP BY category ORDER BY curr DESC` | `dict {chart_data, table_data}` | illimitato (nessun LIMIT) |
| `_fn_spending_by_weekday` (ai_engine.py:217) | `db_path: str, params: dict` | `SELECT date, SUM(amount) FROM transactions WHERE date >= :d GROUP BY date` | `dict {chart_data, table_data}` | illimitato (nessun LIMIT) — poi aggregato in Python per 7 giorni |
| `_fn_category_trend` (ai_engine.py:246) | `db_path: str, params: dict` | `SELECT date, amount FROM transactions WHERE category = :cat AND date >= :d ORDER BY date` | `dict {chart_data, table_data}` | illimitato (nessun LIMIT) |
| `_fn_year_end_forecast` (ai_engine.py:264) | `db_path: str, params: dict` | `SELECT SUM(amount) FROM transactions WHERE date >= :d` (×2) | `dict {chart_data, table_data}` | scalare (2 query aggreganti) |
| `_fn_summary_stats` (ai_engine.py:299) | `db_path: str, params: dict` | `SELECT SUM(amount), COUNT(*), AVG(amount) FROM transactions WHERE date >= :d` / `SELECT category FROM transactions WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1` | `dict {chart_data, table_data}` | 1 (top categoria) |
| `get_anomalies` (ai_engine.py:604) | nessuno | `SELECT id, amount, category, description, date FROM transactions WHERE date >= :d ORDER BY date DESC` | `list[dict]` | 5 (`.anomalies[:5]` a riga 643) |

---

## 3. CONTROLLI DETERMINISMO

### Chiamata LLM #1 — Router/Selector (`_select_function`, ai_engine.py:485)

| Parametro | Valore | Riga |
|---|---|---|
| `model` | `llama-3.3-70b-versatile` | ai_engine.py:13 |
| `temperature` | `0` | ai_engine.py:495 |
| `max_tokens` | `200` | ai_engine.py:496 |
| `seed` | non presente nel codice | — |
| `response_format` | non presente nel codice (testo libero) | — |
| Validazione post-parse | `_parse_ai_response()` con `json.loads` + fallback regex + fallback regex answer/followup. In caso di parse fallito totale: ritorna `{"answer": raw, "followup_questions": []}`. Nessun Pydantic, nessun schema validation sul dict risultante. | ai_engine.py:515-542 |

### Chiamata LLM #2a — Interpret results (`_interpret_results`, ai_engine.py:501)

| Parametro | Valore | Riga |
|---|---|---|
| `model` | `llama-3.3-70b-versatile` | ai_engine.py:13 |
| `temperature` | `0.3` | ai_engine.py:509 |
| `max_tokens` | `500` | ai_engine.py:510 |
| `seed` | non presente nel codice | — |
| `response_format` | non presente nel codice (testo libero) | — |
| Validazione post-parse | identica a `_parse_ai_response()` (stessa funzione) | ai_engine.py:515-542 |

### Chiamata LLM #2b — Risposta testuale in-perimeter (`_answer_in_perimeter`, ai_engine.py:471)

| Parametro | Valore | Riga |
|---|---|---|
| `model` | `llama-3.3-70b-versatile` | ai_engine.py:13 |
| `temperature` | `0.3` | ai_engine.py:479 |
| `max_tokens` | `400` | ai_engine.py:480 |
| `seed` | non presente nel codice | — |
| `response_format` | non presente nel codice (testo libero) | — |
| Validazione post-parse | identica a `_parse_ai_response()` | ai_engine.py:515-542 |

### Chiamata LLM — Briefing (`generate_briefing`, ai_engine.py:564)

| Parametro | Valore | Riga |
|---|---|---|
| `model` | `llama-3.3-70b-versatile` | ai_engine.py:13 |
| `temperature` | `0.2` | ai_engine.py:578 |
| `max_tokens` | `600` | ai_engine.py:579 |
| `seed` | non presente nel codice | — |
| `response_format` | non presente nel codice (testo libero) | — |
| Validazione post-parse | `json.loads(raw)` + fallback regex `\{[\s\S]*\}`. Se entrambi falliscono: `result = None` → ritorna fallback statico. Controlla presenza chiave `"insights"` prima di salvare in cache. | ai_engine.py:583-593 |

---

## 4. CONTROLLI LUNGHEZZA

| Limite | Valore | Fonte | Riga |
|---|---|---|---|
| Limite caratteri input utente (lato schema Pydantic) | `min_length=1` — nessun `max_length` definito | schemas.py:52 | — |
| Limite caratteri input utente (lato frontend) | non presente nel codice | ChatInterface.tsx | — |
| Messaggi history passati al LLM (router call) | **ultimi 2** messaggi di tipo `role=="user"` estratti da `history[-2:]` | ai_engine.py:488-491 | — |
| Messaggi history inviati dal frontend | **tutti** i messaggi in `messages[]` (nessun bound): `messages.map(m => ({role, content}))` | ChatInterface.tsx:212 | — |
| Truncation di `data_summary` (per interpret) | `[:15]` sugli item del grafico e `[:15]` sulle righe della tabella in `_format_data_for_interpretation` | ai_engine.py:439, ai_engine.py:445 | — |
| Truncation di `compact_context` | LIMIT 5 sulle categorie nella query SQL | ai_engine.py:464 | — |
| Truncation di `followup_questions` | `[:2]` all'output di `chat_with_ai` | ai_engine.py:672, ai_engine.py:681 | — |
| Truncation del contesto briefing (`build_context`) | nessuna — la query categorie non ha LIMIT; tutte le categorie degli ultimi 30gg vengono incluse | ai_engine.py:67-70 | — |
| Limite `n` in `top_transactions` | default 10, parametrizzato dall'LLM router, nessun cap massimo nel codice | ai_engine.py:165 | — |

---

## 5. PUNTI FRAGILI

### 5.1 — Risposta LLM malformata può causare 500

**ai_engine.py:646-682 / chat.py:15-18**
`chat_with_ai()` chiama `_select_function()` che chiama `_parse_ai_response()`. Se il parse fallisce completamente, `_parse_ai_response` ritorna `{"answer": raw, "followup_questions": []}`. Il codice poi esegue:
```python
use_function = selector.get("use_function")   # None
in_perimeter = selector.get("in_perimeter", True)  # True (default)
```
Se il router restituisce JSON malformato ma `_parse_ai_response` riesce a estrarre qualcosa senza chiave `in_perimeter`, il default `True` porta al Branch C (risposta testuale) invece che al Branch B o al fuori-perimetro. Non è un 500 diretto, ma il comportamento è silenziosamente errato.

**ai_engine.py:659 — `use_function` non validato come dict prima di `.get()`**
Il codice controlla `if use_function and isinstance(use_function, dict)` (riga 659), quindi questo specifico caso è protetto. Se però il LLM ritorna `"use_function": "stringa"` invece di un oggetto, `isinstance` fallisce e si cade su Branch C senza errore.

**generate_briefing, ai_engine.py:587**
```python
result = json.loads(m.group()) if m else None
```
Se `m` è None (regex non trova `{...}`), `result = None`. Poi il controllo `if result and "insights" in result` non salva in cache e ritorna il fallback. Non è un 500, ma se `json.loads(m.group())` lancia un'eccezione ulteriore, viene catturata dall'`except Exception: pass` esterno (riga 593). Silenzioso, nessun log.

**chat.py:15-18 — catch generico**
```python
except Exception as e:
    raise HTTPException(500, f"Errore AI: {str(e)}")
```
Qualsiasi eccezione non gestita dentro `chat_with_ai` (inclusi errori di rete Groq, timeout, SQLAlchemy) ritorna un 500 con il messaggio dell'eccezione esposto al client.

### 5.2 — Input lungo può gonfiare i token in modo incontrollato

**ChatInterface.tsx:212 — history non bounded**
```typescript
const history = messages.map((m) => ({ role: m.role, content: m.content }));
```
Tutti i messaggi accumulati nella sessione frontend vengono inviati al backend. In una sessione lunga con molti messaggi verbosi, il payload HTTP e i token del router call crescono linearmente senza limite.

**ai_engine.py:52 — `build_context()` senza LIMIT sulla query categorie**
```python
cat_30 = _q(
    "SELECT category, COUNT(*), SUM(amount), AVG(amount) FROM transactions "
    "WHERE date >= :d GROUP BY category ORDER BY SUM(amount) DESC",
    {"d": d30}
)
```
Nessun LIMIT: se l'utente ha molte categorie distinte, l'intera lista viene serializzata nel system prompt di `generate_briefing`. Con 50 categorie la stringa può crescere a diverse centinaia di token non pianificati.

**ai_engine.py:435-447 — `_format_data_for_interpretation()` con truncation a 15 righe**
Il cap a 15 item limita parzialmente il problema, ma `_fn_category_trend` e `_fn_daily_trend` possono produrre decine o centinaia di punti dati (`fetchall()` senza LIMIT). Solo i primi 15 vengono mandati all'LLM, ma tutti vengono estratti dal DB.

### 5.3 — Il router può cadere su ramo testuale per domande fuori perimetro

**ai_engine.py:351-372 / FUNCTION_SELECTOR_PROMPT**
Il prompt del router descrive il Caso 3 come:
```
CASO 3 — domanda NON finanziaria (cucina, sport, coding, ecc.):
{"use_function": null, "in_perimeter": false}
```
Con `temperature=0` il router è molto stabile, ma se il modello non riconosce con certezza una domanda come fuori perimetro (es. "qual è il miglior investimento in crypto?" o "come faccio a fare il budget per le vacanze?"), può restituire `in_perimeter=true` con `use_function=null`, causando il Branch C. In questo branch, `_answer_in_perimeter()` riceve il contesto finanziario dell'utente e risponde liberamente con `temperature=0.3`, senza alcun guard ulteriore sul perimetro dell'output. Il LLM può quindi rispondere a domande su argomenti come finanza personale generica, investimenti, crypto, salute finanziaria — aree non modellate dal sistema ma che passano il filtro `in_perimeter=true`.

**Comportamento attuale**: il sistema non ha un secondo livello di guardia dopo il router. Se `in_perimeter=true` e `use_function=null`, la risposta è affidata interamente al LLM con il contesto dati dell'utente, senza restrizioni aggiuntive.

---

## 6. STIMA TOKEN

### Scenario base: history vuota, domanda di 50 caratteri (~12 token)

#### Chiamata LLM #1 — Router (`_select_function`)

| Componente | Stima token |
|---|---|
| System prompt `FUNCTION_SELECTOR_PROMPT` (riga 351-372) | ~320 token (testo del prompt: ~1280 caratteri) |
| History passata: `history[-2:]` con history vuota | 0 token |
| Domanda utente (50 caratteri) | ~12 token |
| **Totale input** | **~332 token** |
| Output (`max_tokens=200`, tipicamente JSON breve ~80 caratteri) | ~20 token |
| **Costo stimato** | input: 332/1M × $0.59 = **$0.000196** / output: 20/1M × $0.79 = **$0.0000158** |

#### Branch B — Chiamata LLM #2 — Interpret results (`_interpret_results`)

`_format_data_for_interpretation` con truncation a 15 righe. Esempio con `spending_by_category` (8 categorie):

| Componente | Stima token |
|---|---|
| System prompt `INTERPRET_PROMPT` con domanda e data_summary embedded (riga 376-394) | ~200 token (prompt fisso) + ~12 token (domanda) + ~120 token (8 categorie × ~15 token/riga) = ~332 token |
| Messaggio user fisso `"Analizza."` | 3 token |
| **Totale input** | **~335 token** |
| Output (`max_tokens=500`, risposta tipica JSON ~200 token) | ~200 token |
| **Costo stimato** | input: 335/1M × $0.59 = **$0.000198** / output: 200/1M × $0.79 = **$0.000158** |

**Totale Branch B (2 chiamate):**
- Input: ~667 token → $0.000394
- Output: ~220 token → $0.000174
- **Totale: ~$0.000568 per richiesta**

#### Branch C — Chiamata LLM #2 — Risposta testuale (`_answer_in_perimeter`)

`build_compact_context()` con LIMIT 5 categorie: output tipico ~100 caratteri (~25 token).

| Componente | Stima token |
|---|---|
| System prompt `TEXT_ANSWER_PROMPT` con compact_context embedded (riga 398-413) | ~220 token (prompt fisso) + ~25 token (compact_context) = ~245 token |
| Domanda utente (50 caratteri) | ~12 token |
| **Totale input** | **~257 token** |
| Output (`max_tokens=400`, risposta tipica JSON ~150 token) | ~150 token |
| **Costo stimato** | input: 257/1M × $0.59 = **$0.000152** / output: 150/1M × $0.79 = **$0.000119** |

**Totale Branch C (2 chiamate):**
- Input: ~589 token → $0.000348
- Output: ~170 token → $0.000134
- **Totale: ~$0.000482 per richiesta**

#### Branch A — Fuori perimetro (solo 1 chiamata)

- Input: ~332 token → $0.000196
- Output: ~20 token → $0.0000158
- **Totale: ~$0.000212 per richiesta**

### Riepilogo costi

| Branch | N. chiamate LLM | Token input totali | Token output totali | Costo stimato/richiesta |
|---|---|---|---|---|
| A — fuori perimetro | 1 | ~332 | ~20 | ~$0.000212 |
| B — funzione preconfezionata | 2 | ~667 | ~220 | ~$0.000568 |
| C — testo in-perimeter | 2 | ~589 | ~170 | ~$0.000482 |

Prezzi riferimento Groq Llama 3.3 70B: input $0.59/1M token, output $0.79/1M token.
Nota: nessuna funzionalità di prompt caching è configurata nel codice (non presente nel codice).
