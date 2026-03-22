import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.core.database import init_db
from backend.api.routes import transactions, analytics, chat, budgets

app = FastAPI(
    title="FinCopilot API",
    description="API per il copilota finanziario con AI analitica",
    version="1.0.0",
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

# Routes
app.include_router(transactions.router)
app.include_router(analytics.router)
app.include_router(chat.router)
app.include_router(budgets.router)


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
