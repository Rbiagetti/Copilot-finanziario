import os
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, Text, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/fincopilot.db")

# In locale si può forzare un DB di sviluppo senza toccare le credenziali di
# produzione nel .env: se DEV_DATABASE_URL è impostata e non siamo su Render,
# ha priorità su DATABASE_URL. Esempio: sqlite:///./data/fincopilot_dev.db
if os.getenv("DEV_DATABASE_URL") and not os.getenv("RENDER"):
    DATABASE_URL = os.getenv("DEV_DATABASE_URL")

# psycopg2 vuole "postgresql://" ma Supabase/Render forniscono "postgres://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")

# Avviso esplicito: il .env di sviluppo punta spesso al Postgres di produzione.
# Non blocchiamo l'avvio (servono dati reali per alcune verifiche), ma rendiamo
# impossibile farlo in silenzio.
if not _is_sqlite and not os.getenv("RENDER"):
    print(
        "⚠️ [DB] DATABASE_URL punta a Postgres mentre l'app gira in locale: "
        "i test manuali scrivono sul database reale. Imposta DEV_DATABASE_URL "
        "(es. sqlite:///./data/fincopilot_dev.db) per isolarti."
    )

_pg_kwargs = {} if _is_sqlite else {
    # Testa ogni connessione prima di usarla — scarta quelle stale
    "pool_pre_ping": True,
    # Ricicla le connessioni ogni 10 min per evitare il timeout lato Postgres
    "pool_recycle": 600,
    # Pool dimensionato per un'app single-tenant
    "pool_size": 5,
    "max_overflow": 10,
}

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    **_pg_kwargs,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=False)
    subcategory = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    date = Column(String, nullable=False)
    time = Column(String, nullable=True)
    account = Column(String, default="principale")
    tags = Column(Text, nullable=True)
    source = Column(String, default="manual")
    is_recurring = Column(Boolean, default=False, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    period = Column(String, default="monthly")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class Category(Base):
    """Categorie personalizzate aggiunte dall'utente (le 10 standard restano hardcoded in
    api/models/schemas.py, non toccabili — vive solo qui l'aggiunta, mai la sostituzione).
    Cancellazione = soft delete (active=False), stesso pattern già usato per Budget: le
    transazioni storiche mantengono la categoria intatta, la categoria disattivata sparisce
    solo dai menu per le nuove transazioni."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    name = Column(String, nullable=False)  # normalizzato lowercase, coerente con Transaction.category
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class WealthAccount(Base):
    """Conto del patrimonio (MPS, Trade Republic, contanti...). L'utente li crea,
    rinomina e archivia liberamente: il nome è testo libero, `kind` è uno slug usato
    solo per la composizione del patrimonio. Archiviazione = soft delete, stesso
    pattern di Category/Budget: lo storico resta in DB ma non viene più conteggiato."""
    __tablename__ = "wealth_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False, default="liquidita")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class WealthSnapshot(Base):
    """Saldo di un conto a una certa data (ISO YYYY-MM-DD, coerente con Transaction.date).
    Una "foto" del patrimonio è l'insieme degli snapshot salvati sulla stessa data. Il
    vincolo univoco (account_id, snapshot_date) rende il salvataggio un upsert idempotente.
    user_id è duplicato dall'account per filtrare senza join e per difesa in profondità."""
    __tablename__ = "wealth_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_date", name="uq_wealth_snapshot_account_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    account_id = Column(Integer, ForeignKey("wealth_accounts.id"), nullable=False, index=True)
    balance = Column(Float, nullable=False)
    snapshot_date = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.now)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, index=True)  # Supabase UUID
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class UserSettings(Base):
    """Preferenze per-utente. Se ai_model è null, l'utente usa il default globale
    (backend.core.ai_engine.DEFAULT_MODEL) — solo chi vuole scegliere un modello
    diverso ha una riga con ai_model valorizzato."""
    __tablename__ = "user_settings"

    user_id = Column(String(36), primary_key=True)  # Supabase UUID
    ai_model = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
