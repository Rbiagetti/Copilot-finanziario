# FinCopilot Auth Audit — Fase 0

**Status**: READ-ONLY / AUDIT  
**Data**: 2026-04-28  
**Obiettivo**: Audit completo di autenticazione/autorizzazione + piano multiutenza

---

## SEZIONE 1: MODELLO UTENTI ATTUALE

### 1a) Tabella Users
**STATO**: NON ESISTE  
- Nessuna tabella `users` nel database  
- L'autenticazione è delegata completamente a **Supabase**  
- Gli user_id sono UUID forniti da Supabase (es. `40e904f5...`)

**Implicazioni**:
- Non c'è controllo locale di password/hash
- Ogni token valido = utente autenticato
- Nessun tracciamento locale di utenti

### 1b) Metodo di Autenticazione
**METODO**: JWT via Supabase (OAuth/email-based)  
**DOVE**: 
- **Backend**: `backend/api/auth.py::get_current_user()` valida il token verso l'API Supabase
- **Frontend**: `frontend/src/store/authStore.ts` gestisce sessione via Supabase client
- **Token storage**: HttpOnly cookie (gestito da Supabase SDK)

**Flusso**:
1. Frontend chiama `supabase.auth.signIn(email, password)`
2. Supabase ritorna un token JWT e lo salva in HttpOnly cookie
3. Frontend legge il token con `getToken()` per ogni request API
4. Backend riceve il token in header `Authorization: Bearer {token}`
5. Backend valida il token contro Supabase API (`/auth/v1/user`)
6. Se valido, continua; se no, ritorna 401

### 1c) Contenuto JWT Token
**PAYLOAD** (from Supabase user object):
```json
{
  "id": "40e904f5-...",  // ← Supabase UUID, usato come user_id
  "email": "user@example.com",
  "aud": "authenticated",
  "created_at": "2024-01-15T...",
  ...
}
```

**IMPLEMENTAZIONE**: 
- `backend/api/auth.py` linea 44: `user_id = data.get("id", "unknown")`
- L'user_id è memorizzato in cache per 30 secondi per ridurre load su Supabase

### 1d) Modelli Pydantic
**PASSWORD IN CHIARO**: NO ✅  
- Nessuno schema Pydantic contiene password
- Password non è mai trasmessa dal frontend dopo il login iniziale
- Supabase gestisce tutto lato auth

---

## SEZIONE 2: ISOLAMENTO DATI ATTUALE

### 2a) Colonna user_id
**STATO**: ❌ NON PRESENTE  
- `transactions`: **NO** user_id  
- `budgets`: **NO** user_id  
- `chat_history`: **NO** user_id  

**CRITICO**: Tutte le tabelle di dati privati mancano del campo user_id.

### 2b) Filtraggio Transazioni
**STATO**: ❌ NON IMPLEMENTATO  
**Esempio** (transactions.py::list_transactions linea 43-60):
```python
@router.get("/")
async def list_transactions(..., db: Session = Depends(get_db)):
    q = db.query(Transaction)
    if category:
        q = q.filter(Transaction.category == category)
    # ❌ NON C'È: q.filter(Transaction.user_id == current_user_id)
    return q.all()
```

**RISULTATO**: Qualsiasi utente autenticato vede TUTTE le transazioni di TUTTI gli utenti.

**BUCO DI SICUREZZA**: CRITICO ⛔

### 2c) Tipo di Filtraggio
**ATTUALE**: Nessuno  
**IDEALE**: SQL parametrizzato  
**ANALISI**:
```
SQLAlchemy.query().filter() usa parametri prepared statement ✅
Non c'è SQL injection risk dal lato sintassi
MA il filtro per user_id è completamente assente
```

### 2d) Tabelle Senza user_id
| Tabella | Colonne Attuali | Dovrebbe avere user_id? | Critico? |
|---------|-----|---|---|
| transactions | id, amount, category, date, time, account, tags, source, is_recurring, created_at, updated_at | **SÌ** | ⛔ CRITICO |
| budgets | id, category, amount, period, active, created_at | **SÌ** | ⛔ CRITICO |
| chat_history | id, role, content, metadata_json, created_at | **SÌ** | ⚠️ RILEVANTE |

---

## SEZIONE 3: DEPENDENCY INJECTION AUTH

### 3a) get_current_user()
**ESISTE**: SÌ ✅  
**POSIZIONE**: `backend/api/auth.py::get_current_user()`  
**TIPO**: Dependency FastAPI  
**USO**: Registrata a livello router in `main.py`

### 3b) 5 Endpoint — Verifica Autenticazione
| Route | File | Ha get_current_user? | Status |
|-------|------|---|---|
| POST /transactions | transactions.py:21 | ❌ NO | Protetto globalmente |
| GET /transactions | transactions.py:43 | ❌ NO | Protetto globalmente |
| GET /analytics/dashboard | analytics.py:22 | ❌ NO | Protetto globalmente |
| GET /budgets | budgets.py:? | ❌ NO | Protetto globalmente |
| GET /ai/anomalies | ai.py:? | ❌ NO | Protetto globalmente |

**ANALISI**:
- ✅ TUTTE le route private sono protette da JWT (dipendenza globale in main.py linea 39-44)
- ❌ NESSUNA route riceve `current_user_id` come parametro
- ⚠️ Il token è validato, ma l'user_id non è disponibile alle route

### 3c) Route Senza Autenticazione
**CORRETTE**:
- `/api/v1/health` — pubblica ✅
- `/docs` — pubblica ✅
- `/openapi.json` — pubblica ✅

**MALFORMATE**: Nessuna rotta privata scoperta senza autenticazione

---

## SEZIONE 4: RATE LIMITING E CONCORRENZA

### 4a) Rate Limiter Globale
**ESISTE**: ❌ NO  
- Nessun middleware rate limiting presente
- Nessun decoratore `@limiter` sulle route

### 4b) Tipo di Rate Limit
**N/A**: Non esiste

### 4c) Impatto Multiutenza
**PROBLEMA**: Senza rate limiting per utente, un singolo utente può fare spam e degradare il servizio per gli altri.
- 1000 request/secondo da user A → API lenta per user B
- Brute force su login possibile (se login fosse implementato localmente)

### 4d) Lock Pessimistico SQLAlchemy
**STATO**: ❌ NON USATO  
- Nessun `.with_for_update()` nelle query
- Nessun `db.begin()` per transazioni atomiche

**IMPATTO**: 
- Race condition possibile su operazioni critiche (budget allocation)
- Due utenti che modificano lo stesso budget contemporaneamente potrebbero corrompere i dati

---

## SEZIONE 5: COLONNE MULTI-UTENTE — CHECKLIST

| Tabella | user_id? | Dovrebbe? | Critico? | Note |
|---------|------|---|---|---|
| transactions | ❌ NO | ✅ SÌ | ⛔ CRITICO | Dati finanziari personali |
| budgets | ❌ NO | ✅ SÌ | ⛔ CRITICO | Dati finanziari personali |
| chat_history | ❌ NO | ✅ SÌ | ⚠️ RILEVANTE | Contesto conversazione |
| users | ❌ NO (tabella non esiste) | ✅ SÌ | ⛔ CRITICO | Fonte di verità per utenti |

---

## SEZIONE 6: ERRORI DIMOSTRATI / VULNERABILITÀ

### 6a) Modifica Token
**SCENARIO**: Utente modifica il token JWT e cambia `sub` (user_id)
**RISPOSTA ATTUALE**: Il backend non validerebbe il token (firma Supabase è verificata)
**RISULTATO**: ✅ SICURO — JWT firmato, non modificabile senza la chiave privata di Supabase

### 6b) Race Condition
**SCENARIO**: Due utenti fanno una query nello stesso millisecondo
**TABELLE AFFETTE**: Tutte  
**TIPO**: SELECT race condition su `budgets` (due utenti leggono budget, entrambi decrementano, save sovrascrive)
**IMPATTO**: ⛔ CRITICO — bilanci corrotti

**Esempio**:
```
Budget iniziale: €100
User A legge → €100
User B legge → €100
User A decrementa di €30 → salva €70
User B decrementa di €50 → salva €50
Risultato: €50 invece di €20 (dovrebbe essere €100 - €30 - €50)
```

### 6c) Dati Esposti nelle Risposte
**DATI NELLA API**:
- `forecasted_total` (forecast)
- `anomalies` con rilevazioni
- `budgets` con spendings
- Top 10 transazioni

**DOVREBBERO ESSERE ESPOSTI**: SÌ ✅  
**FILTRO MANCANTE**: SÌ ⛔  
→ Ogni utente vede i dati di TUTTI gli utenti

---

## SEZIONE 7: FRONTEND — TOKEN STORAGE E TRASMISSIONE

### 7a) Token Storage
**DOVE**: HttpOnly Cookie (managed by Supabase SDK) + memorizzato temporaneamente in `sessionStorage` dal Supabase client
**SICUREZZA**: ✅ BUONA
- HttpOnly → XSS non può rubare il cookie
- Supabase SDK gestisce il refresh automatico

### 7b) Trasmissione nelle Request
**METODO**: 
```typescript
// frontend/src/api/client.ts
api.interceptors.request.use(async (config) => {
  const token = await getToken();
  config.headers["Authorization"] = `Bearer {token}`;
  return config;
});
```
**SICUREZZA**: ✅ CORRETTA — Header Authorization, non query param

### 7c) Refresh Token
**ESISTE**: SÌ ✅ (gestito da Supabase)  
**COME**: Supabase gestisce automaticamente il refresh tramite HTTP-only cookie
**BEHAVIOR**: 
- Token breve (15 min) + refresh token lungo-vivuto
- Al scadere, Supabase rinnova automaticamente se il refresh token è valido
- Logout invalida il refresh token nel backend Supabase

---

## SEZIONE A: MODELLO AUTH PROPOSTO

### A1: User Table (da creare)
```python
class User(Base):
    __tablename__ = "users"
    
    # Identificazione univoca (da Supabase)
    id = Column(String(36), primary_key=True)  # Supabase UUID
    email = Column(String(255), unique=True, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
```

### A2: Token Payload (JWT)
```json
{
  "sub": "40e904f5-aaaa-bbbb-cccc-...",  // user_id di Supabase
  "email": "user@example.com",            // informativo
  "iat": 1704067200,                      // emesso a
  "exp": 1704153600,                      // scadenza (15 min)
  "aud": "authenticated"
}
```

### A3: Colonne Critiche nelle Tabelle
Ogni tabella con dati privati DEVE avere:
```python
# Compound primary key
user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
id = Column(Integer, primary_key=True, autoincrement=True)

# Indice per query veloci per utente
__table_args__ = (
    Index("idx_user_id", "user_id"),
)
```

---

## SEZIONE B: ISOLAMENTO DATI — REGOLE

### B1: WHERE Clause Obbligatoria
REGOLA ASSOLUTA: Ogni query SU DATI PRIVATI deve avere:
```python
stmt = select(Transaction).where(
    (Transaction.user_id == current_user_id) &
    (Transaction.category == "cibo")
)
```
❌ VIETATO: `select(Transaction)` senza filtro user_id

### B2: Dependency Injection
Ogni route privata DEVE ricevere user_id:
```python
@router.get("/transactions")
async def list_transactions(
    current_user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[TransactionResponse]:
    # user_id è garantito dal token, nessuna possibilità di bypass
```

### B3: Query Parametrizzate
```python
# ✅ SICURO
stmt = select(Transaction).where(Transaction.user_id == current_user_id)

# ❌ VIETATO (SQL injection)
stmt = f"SELECT * FROM transactions WHERE user_id = '{current_user_id}'"
```

---

## SEZIONE C: DEPENDENCY INJECTION — IMPLEMENTAZIONE

```python
# backend/core/auth.py (già esiste con Supabase)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())) -> str:
    """
    Valida JWT contro Supabase, ritorna user_id.
    Solleva HTTPException 401 se token invalido.
    
    Cache 30 secondi per evitare troppe chiamate a Supabase.
    """
    # Implementazione già in backend/api/auth.py
    # Ritorna user_id: str (Supabase UUID)
```

**Registrazione** (già corretta in main.py):
```python
app.include_router(
    transactions.router,
    dependencies=[Depends(get_current_user)]  # ← valida il token
)
```

**Accesso nelle route** (DA AGGIUNGERE):
```python
@router.get("/")
async def list_transactions(
    current_user_id: str = Depends(get_current_user),  # ← DA AGGIUNGERE
    db: Session = Depends(get_db)
) -> List[TransactionResponse]:
    # Usa current_user_id per filtrare
```

---

## SEZIONE D: RATE LIMITING PER UTENTE

### D1: Requisiti
- [ ] Limite: 100 request/minuto per utente
- [ ] Limite brute-force: 5 tentativi/minuto su /auth/login
- [ ] Risposta: 429 Too Many Requests

### D2: Implementazione Consigliata
```python
# Installa: pip install slowapi

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=lambda request: get_current_user_id(request),  # per user
    default_limits=["100/minute"]
)

@app.get("/transactions")
@limiter.limit("100/minute")
async def list_transactions(...):
    pass
```

---

## SEZIONE E: CONCORRENZA — LOCK PESSIMISTICO

### E1: Scenario Critico
```python
# ❌ RACE CONDITION
budget = db.query(Budget).filter(...).first()
if budget.remaining >= amount:
    budget.remaining -= amount
    db.commit()
```

Due utenti simultanei → entrambi leggono `€100`, entrambi salvano `€70`.

### E2: Fix — with_for_update()
```python
# ✅ SAFE
budget = db.query(Budget)\
    .filter(Budget.user_id == user_id)\
    .with_for_update()\
    .first()

if budget.remaining >= amount:
    budget.remaining -= amount
    db.commit()
```

Lock pessimistico: il secondo utente aspetta che il primo finisca.

---

## SEZIONE F: CHECKLIST SICUREZZA

- [ ] Password hashed con argon2 (Supabase lo fa)
- [ ] Token JWT con exp ≤ 15 minuti ✅
- [ ] Refresh token separato e revocabile ✅
- [ ] Logout invalida refresh token ✅
- [ ] CORS ristretto (non `*`) ✅
- [ ] HTTPS obbligatorio in produzione ✅
- [ ] Secure flag su cookie ✅
- [ ] SameSite=Strict ✅
- [ ] HTTPOnly=True ✅
- [ ] Rate limiting per utente ❌
- [ ] Rate limiting su login ❌
- [ ] Validation email format ✅
- [ ] Password min 8 char (Supabase) ✅
- [ ] Nessun log di password/token ✅
- [ ] Test isolamento dati ❌
- [ ] Test concorrenza ❌

---

## PIANO DI ESECUZIONE — FASE 1 (ITERATIVO, ZERO DOWNTIME)

### Passo 1: Preparazione (nessuna modifica DB)
- [ ] Leggere completamente `backend/api/auth.py` per capire il caching
- [ ] Scrivere funzione helper per estrarre `current_user_id` dalle route
- [ ] Scrivere 3 test di isolamento per verificare il fix

### Passo 2: Aggiunta Colonna user_id (migration reversibile)
- [ ] Crea migration Alembic: `alembic revision --autogenerate -m "add user_id to transactions"`
- [ ] Aggiungi colonna `user_id` a `transactions`
- [ ] Aggiungi colonna `user_id` a `budgets`
- [ ] Aggiungi colonna `user_id` a `chat_history`
- [ ] Rendi `user_id NOT NULL` con default per i dati esistenti
- [ ] Aggiungi Foreign Key e indice

### Passo 3: Auth Checks Graduale (una route per volta)
- [ ] Aggiungi `current_user_id: str = Depends(get_current_user)` a `GET /transactions`
- [ ] Aggiungi filtro `WHERE user_id == current_user_id`
- [ ] Testa: token valido → dati filtrati; token invalido → 401
- [ ] Repeat per `POST /transactions`, `PUT /transactions/{id}`, etc.

### Passo 4: Frontend Auth
- [ ] Verifica che il token sia passato in `Authorization` header
- [ ] Testa con due browser diversi che i dati siano separati

### Passo 5: Rate Limiting
- [ ] Installa `slowapi`
- [ ] Configura `limiter` per utente
- [ ] Applica a tutte le route private

### Passo 6: Test Isolamento
- [ ] Scrivi `tests/test_multiuser_isolation.py`
- [ ] Test: User A crea tx, User B non la vede
- [ ] Test: User A non può accedere a `/transactions/{id}` di User B (401)
- [ ] Test: Due utenti simultanei su budget non corrompono dati

---

## VINCOLI ASSOLUTI

❌ **VIETATO COMPLETAMENTE**:
1. Password in plaintext — MAI
2. user_id in query string (`?user_id=123`) — sempre nel token
3. SELECT senza `WHERE user_id = current_user_id` su dati privati
4. CORS aperto (`Access-Control-Allow-Origin: *`)
5. Token con scadenza > 1 ora
6. Refresh token senza expiry
7. Eccezione che scopre se l'email esiste (timing attack)
8. Log di token, password, dati sensibili

---

## RIEPILOGO VULNERABILITÀ TROVATE

| Severity | Problema | Posizione | Fix |
|----------|----------|-----------|-----|
| ⛔ CRITICO | Nessun user_id in tabelle | transactions, budgets, chat_history | Aggiungere colonna + FK |
| ⛔ CRITICO | Query non filtrano per user_id | analytics.py, transactions.py | Aggiungere Depends(get_current_user) + WHERE |
| ⛔ CRITICO | Race condition possibile | budgets (concurrent modify) | Aggiungere .with_for_update() |
| ⚠️ ALTO | Nessun rate limiting | main.py | Installare slowapi |
| 🟡 MEDIO | Nessun test isolamento | N/A | Scrivere test suite |

---

**Documento creato in stato READ-ONLY.**  
**Prossima fase**: Implementazione Passo 1 (Preparazione) quando approvato.
