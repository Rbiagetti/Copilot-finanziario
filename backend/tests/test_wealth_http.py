"""Smoke test HTTP del Wealth Monitor con TestClient.

Serve anche da regressione per la compatibilità TestClient/httpx: con httpx 0.28
starlette passava `app=` a `httpx.Client` (argomento rimosso) e ogni test HTTP
esplodeva. Il pin a httpx 0.27.2 in requirements.txt mantiene questo percorso
utilizzabile per i moduli futuri.
"""
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api.auth import get_current_user
from backend.api.routes.wealth import router as wealth_router
from backend.core.database import Base, get_db


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    app = FastAPI()
    app.include_router(wealth_router)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: "http-user"

    with TestClient(app) as test_client:
        yield test_client

    Base.metadata.drop_all(engine)
    engine.dispose()


def test_wealth_http_flow(client):
    created = client.post(
        "/api/v1/wealth/accounts", json={"name": "MPS", "kind": "liquidita"}
    )
    assert created.status_code == 201
    account_id = created.json()["id"]

    day = (date.today() - timedelta(days=1)).isoformat()
    saved = client.put(
        "/api/v1/wealth/snapshot",
        json={"date": day, "entries": [{"account_id": account_id, "balance": 1234.5}]},
    )
    assert saved.status_code == 200

    overview = client.get("/api/v1/wealth/overview")
    assert overview.status_code == 200
    assert overview.json()["current"]["total"] == 1234.5

    accounts = client.get("/api/v1/wealth/accounts")
    assert [account["name"] for account in accounts.json()] == ["MPS"]


def test_wealth_http_rejects_future_date(client):
    created = client.post(
        "/api/v1/wealth/accounts", json={"name": "MPS", "kind": "liquidita"}
    )
    account_id = created.json()["id"]

    future = (date.today() + timedelta(days=1)).isoformat()
    response = client.put(
        "/api/v1/wealth/snapshot",
        json={"date": future, "entries": [{"account_id": account_id, "balance": 1}]},
    )
    assert response.status_code == 422
