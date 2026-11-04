"""Regressioni per transazioni e budget.

Coprono i bug reali emersi il 2026-11-04:
  - la modifica dell'ora veniva ignorata (campo assente da `TransactionUpdate`);
  - date/importi non venivano validati in scrittura;
  - il totale del budget includeva anche le transazioni del mese successivo.

Le date future **dentro il mese corrente** sono volute (spese pianificate): i test
verificano che restino conteggiate, mentre quelle del mese dopo no.

Nessuna API key e nessun DB reale: SQLite in memoria, route chiamate direttamente.
"""
import asyncio
import calendar
from datetime import date, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.models.schemas import TransactionCreate, TransactionUpdate
from backend.api.routes.budgets import budget_status
from backend.api.routes.transactions import create_transaction, update_transaction
from backend.core.database import Base, Budget, Transaction

TODAY = date.today()
FUTURE = (TODAY + timedelta(days=10)).isoformat()


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _add_tx(db, day, amount=10.0, category="cibo", user="user-a", time=None):
    tx = Transaction(
        user_id=user,
        amount=amount,
        category=category,
        date=day,
        time=time,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


# ─── Validazione input ────────────────────────────────────────────────────────

class TestTransactionValidation:
    def test_update_accepts_and_normalizes_time(self):
        updates = TransactionUpdate(time="9:05")
        assert updates.model_dump(exclude_unset=True) == {"time": "09:05"}

    def test_create_allows_normalized_future_date(self):
        data = TransactionCreate(amount=10, category="cibo", date=FUTURE)
        assert data.date == FUTURE

    def test_rejects_malformed_date(self):
        with pytest.raises(ValidationError):
            TransactionCreate(amount=10, category="cibo", date="04/11/2026")
        with pytest.raises(ValidationError):
            TransactionUpdate(date="2026-13-01")

    def test_rejects_non_positive_amount(self):
        with pytest.raises(ValidationError):
            TransactionUpdate(amount=0)
        with pytest.raises(ValidationError):
            TransactionUpdate(amount=-5)

    def test_rejects_invalid_time(self):
        with pytest.raises(ValidationError):
            TransactionUpdate(time="25:00")


# ─── Modifica transazione ─────────────────────────────────────────────────────

class TestUpdateTransaction:
    def test_persists_time(self, db):
        tx = _add_tx(db, TODAY.isoformat(), time="10:00")

        updated = asyncio.run(
            update_transaction(
                tx.id,
                TransactionUpdate(time="18:30"),
                current_user_id="user-a",
                db=db,
            )
        )

        assert updated.time == "18:30"
        assert db.get(Transaction, tx.id).time == "18:30"

    def test_can_clear_time(self, db):
        tx = _add_tx(db, TODAY.isoformat(), time="10:00")

        updated = asyncio.run(
            update_transaction(
                tx.id,
                TransactionUpdate(time=None),
                current_user_id="user-a",
                db=db,
            )
        )

        assert updated.time is None

    def test_explicit_null_date_keeps_existing_date(self, db):
        tx = _add_tx(db, TODAY.isoformat())

        updated = asyncio.run(
            update_transaction(
                tx.id,
                TransactionUpdate(date=None),
                current_user_id="user-a",
                db=db,
            )
        )

        assert updated.date == TODAY.isoformat()

    def test_cannot_update_another_users_transaction(self, db):
        from fastapi import HTTPException

        tx = _add_tx(db, TODAY.isoformat(), user="user-b")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                update_transaction(
                    tx.id,
                    TransactionUpdate(amount=99),
                    current_user_id="user-a",
                    db=db,
                )
            )
        assert exc.value.status_code == 404


class TestCreateTransaction:
    def test_stores_normalized_date_and_time(self, db):
        tx = asyncio.run(
            create_transaction(
                TransactionCreate(
                    amount=12.5,
                    category="cibo",
                    date="2026-11-4",
                    time="9:05",
                ),
                current_user_id="user-a",
                db=db,
            )
        )

        assert tx.date == "2026-11-04"
        assert tx.time == "09:05"


# ─── Budget mensile e date future ─────────────────────────────────────────────

class TestBudgetMonthBounds:
    def test_counts_planned_expense_this_month_but_not_next_month(self, db):
        last_day = TODAY.replace(day=calendar.monthrange(TODAY.year, TODAY.month)[1])
        if TODAY.month == 12:
            next_month = date(TODAY.year + 1, 1, 1)
        else:
            next_month = date(TODAY.year, TODAY.month + 1, 1)

        _add_tx(db, TODAY.isoformat(), amount=100.0)

        expected = 100.0
        # Spesa pianificata più avanti nello stesso mese: deve contare.
        if last_day > TODAY:
            _add_tx(db, last_day.isoformat(), amount=50.0)
            expected += 50.0

        # Spesa del mese successivo: non deve entrare nel budget di questo mese.
        _add_tx(db, next_month.isoformat(), amount=999.0)

        db.add(Budget(user_id="user-a", category="cibo", amount=500.0))
        db.commit()

        rows = asyncio.run(budget_status(current_user_id="user-a", db=db))

        assert rows[0]["spent"] == pytest.approx(expected)
