import os
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, Text, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/fincopilot.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
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
    category = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    period = Column(String, default="monthly")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrazione colonne aggiunte dopo la creazione iniziale del DB
    import sqlite3, os
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        existing = [r[1] for r in cur.execute("PRAGMA table_info(transactions)").fetchall()]
        if "is_recurring" not in existing:
            cur.execute("ALTER TABLE transactions ADD COLUMN is_recurring INTEGER DEFAULT 0")
            conn.commit()
        conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
