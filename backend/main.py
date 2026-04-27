import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from backend.core.database import init_db
from backend.api.routes import transactions, analytics, chat, budgets, ai
from backend.api.routes.report import router as report_router
from backend.api.auth import get_current_user

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Azioni all'avvio: inizializziamo il database
    init_db()
    yield
    # Azioni allo spegnimento (se servissero) possono andare qui

app = FastAPI(
    title="FinCopilot API",
    description="API per il copilota finanziario con AI analitica",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes - Protette da JWT Supabase
app.include_router(transactions.router, dependencies=[Depends(get_current_user)])
app.include_router(analytics.router, dependencies=[Depends(get_current_user)])
app.include_router(chat.router, dependencies=[Depends(get_current_user)])
app.include_router(budgets.router, dependencies=[Depends(get_current_user)])
app.include_router(ai.router, dependencies=[Depends(get_current_user)])
app.include_router(report_router, dependencies=[Depends(get_current_user)])

@app.api_route("/api/v1/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
