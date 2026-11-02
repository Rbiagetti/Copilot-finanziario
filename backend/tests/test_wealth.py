"""Test deterministici del Wealth Monitor: CRUD conti, upsert degli snapshot,
calcolo dell'overview, isolamento tra utenti e validazioni.

Nessuna API key e nessun DB reale: SQLite in memoria. Le route sono chiamate
direttamente (senza TestClient) perché starlette e httpx 0.28 sono incompatibili
in questo venv — stesso approccio già usato in test_ai_routing.py.
"""
from datetime import date, timedelta

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.models.schemas import (
    WealthAccountCreate,
    WealthAccountUpdate,
    WealthSnapshotEntry,
    WealthSnapshotSave,
)
from backend.api.routes.wealth import (
    account_history,
    archive_account,
    create_account,
    get_overview,
    get_snapshot,
    list_accounts,
    save_snapshot,
    update_account,
)
from backend.core.database import Base

TODAY = date.today()
DAY_1 = (TODAY - timedelta(days=60)).isoformat()
DAY_2 = (TODAY - timedelta(days=30)).isoformat()
FUTURE = (TODAY + timedelta(days=1)).isoformat()


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


def _create(db, name="MPS", kind="liquidita", user="user-a"):
    return create_account(
        WealthAccountCreate(name=name, kind=kind), current_user_id=user, db=db
    )


def _save(db, day, entries, user="user-a"):
    payload = WealthSnapshotSave(
        date=day, entries=[WealthSnapshotEntry(**entry) for entry in entries]
    )
    return save_snapshot(payload, current_user_id=user, db=db)


def _overview(db, user="user-a", months=12):
    return get_overview(months=months, current_user_id=user, db=db)


# ─── Conti ────────────────────────────────────────────────────────────────────

class TestAccounts:
    def test_create_and_list(self, db):
        account = _create(db, "MPS")
        assert account.name == "MPS"
        assert account.kind == "liquidita"
        assert [a.name for a in list_accounts(current_user_id="user-a", db=db)] == [
            "MPS"
        ]

    def test_duplicate_name_is_case_insensitive(self, db):
        _create(db, "Trade Republic")
        with pytest.raises(HTTPException) as exc:
            _create(db, "trade republic", "investimenti")
        assert exc.value.status_code == 409

    def test_invalid_kind_rejected(self, db):
        with pytest.raises(HTTPException) as exc:
            _create(db, "X", "cripto")
        assert exc.value.status_code == 422

    def test_empty_name_rejected(self, db):
        with pytest.raises(HTTPException) as exc:
            _create(db, "   ")
        assert exc.value.status_code == 422

    def test_rename_and_change_kind(self, db):
        account = _create(db, "Conto vecchio")
        updated = update_account(
            account.id,
            WealthAccountUpdate(name="Conto nuovo", kind="investimenti"),
            current_user_id="user-a",
            db=db,
        )
        assert updated.name == "Conto nuovo"
        assert updated.kind == "investimenti"

    def test_soft_delete_hides_account_but_keeps_history(self, db):
        account = _create(db, "MPS")
        _save(db, DAY_1, [{"account_id": account.id, "balance": 1000}])

        archive_account(account.id, current_user_id="user-a", db=db)
        assert list_accounts(current_user_id="user-a", db=db) == []

        overview = _overview(db)
        assert overview["series"] == []
        assert overview["composition"] == []

        history = account_history(account.id, current_user_id="user-a", db=db)
        assert history["history"] == [{"date": DAY_1, "balance": 1000.0}]


# ─── Snapshot ─────────────────────────────────────────────────────────────────

class TestSnapshots:
    def test_prefill_uses_last_balance_on_or_before_date(self, db):
        account = _create(db, "MPS")
        _save(db, DAY_1, [{"account_id": account.id, "balance": 1000}])

        prefill = get_snapshot(date_str=DAY_2, current_user_id="user-a", db=db)
        assert prefill["accounts"][0]["balance"] == 1000.0
        assert prefill["accounts"][0]["balance_date"] == DAY_1

        earlier = get_snapshot(
            date_str="2000-01-01", current_user_id="user-a", db=db
        )
        assert earlier["accounts"][0]["balance"] is None

    def test_upsert_same_date_does_not_duplicate(self, db):
        account = _create(db, "MPS")
        _save(db, DAY_1, [{"account_id": account.id, "balance": 1000}])
        _save(db, DAY_1, [{"account_id": account.id, "balance": 1250}])

        overview = _overview(db)
        assert len(overview["series"]) == 1
        assert overview["series"][0]["total"] == 1250.0

    def test_future_date_rejected(self, db):
        account = _create(db, "MPS")
        with pytest.raises(HTTPException) as exc:
            _save(db, FUTURE, [{"account_id": account.id, "balance": 100}])
        assert exc.value.status_code == 422

    def test_negative_balance_rejected(self, db):
        with pytest.raises(ValidationError):
            WealthSnapshotEntry(account_id=1, balance=-1)

    def test_duplicate_account_in_payload_rejected(self, db):
        account = _create(db, "MPS")
        with pytest.raises(HTTPException) as exc:
            _save(
                db,
                DAY_1,
                [
                    {"account_id": account.id, "balance": 10},
                    {"account_id": account.id, "balance": 20},
                ],
            )
        assert exc.value.status_code == 422

    def test_archived_account_cannot_be_updated(self, db):
        account = _create(db, "MPS")
        archive_account(account.id, current_user_id="user-a", db=db)
        with pytest.raises(HTTPException) as exc:
            _save(db, DAY_1, [{"account_id": account.id, "balance": 10}])
        assert exc.value.status_code == 404


# ─── Overview ─────────────────────────────────────────────────────────────────

class TestOverview:
    def test_totals_delta_and_composition(self, db):
        mps = _create(db, "MPS", "liquidita")
        tr = _create(db, "Trade Republic", "investimenti")

        _save(
            db,
            DAY_1,
            [
                {"account_id": mps.id, "balance": 1000},
                {"account_id": tr.id, "balance": 500},
            ],
        )
        _save(
            db,
            DAY_2,
            [
                {"account_id": mps.id, "balance": 1200},
                {"account_id": tr.id, "balance": 600},
            ],
        )

        overview = _overview(db)
        assert [point["total"] for point in overview["series"]] == [1500.0, 1800.0]
        assert overview["current"] == {"date": DAY_2, "total": 1800.0}
        assert overview["previous"] == {"date": DAY_1, "total": 1500.0}
        assert overview["delta"] == 300.0
        assert overview["delta_pct"] == 20.0

        composition = {row["kind"]: row for row in overview["composition"]}
        assert composition["liquidita"]["total"] == 1200.0
        assert composition["investimenti"]["total"] == 600.0
        assert composition["liquidita"]["pct"] == 66.7
        assert composition["investimenti"]["pct"] == 33.3

        accounts = {row["name"]: row for row in overview["accounts"]}
        assert accounts["MPS"]["balance"] == 1200.0
        assert accounts["MPS"]["delta"] == 200.0
        assert accounts["Trade Republic"]["delta"] == 100.0

    def test_months_window_limits_series(self, db):
        account = _create(db, "MPS")
        old = (TODAY - timedelta(days=400)).isoformat()
        _save(db, old, [{"account_id": account.id, "balance": 100}])
        _save(db, DAY_1, [{"account_id": account.id, "balance": 200}])

        overview = _overview(db, months=12)
        assert [point["date"] for point in overview["series"]] == [DAY_1]
        # Il saldo attuale resta quello più recente, anche fuori finestra.
        assert overview["accounts"][0]["balance"] == 200.0

    def test_account_without_snapshot_is_zero(self, db):
        _create(db, "Nuovo")
        overview = _overview(db)
        assert overview["series"] == []
        assert overview["accounts"][0]["balance"] == 0.0
        assert overview["accounts"][0]["last_date"] is None


# ─── Multi-tenancy ────────────────────────────────────────────────────────────

class TestIsolation:
    def test_users_do_not_see_each_other(self, db):
        account = _create(db, "MPS")
        _save(db, DAY_1, [{"account_id": account.id, "balance": 1000}])

        assert list_accounts(current_user_id="user-b", db=db) == []
        assert _overview(db, user="user-b")["series"] == []

        with pytest.raises(HTTPException) as patch_exc:
            update_account(
                account.id,
                WealthAccountUpdate(name="Rubato"),
                current_user_id="user-b",
                db=db,
            )
        assert patch_exc.value.status_code == 404

        with pytest.raises(HTTPException) as delete_exc:
            archive_account(account.id, current_user_id="user-b", db=db)
        assert delete_exc.value.status_code == 404

        with pytest.raises(HTTPException) as save_exc:
            _save(
                db,
                DAY_1,
                [{"account_id": account.id, "balance": 999}],
                user="user-b",
            )
        assert save_exc.value.status_code == 404
