import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

from app.database.base import Base
from app.database.session import engine
import app.models  # noqa: F401 — import models so SQLAlchemy registers them

from app.routers import auth, transactions, alerts, analytics, ai, reports
from app.routers import ml as ml_router

logger = logging.getLogger(__name__)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FINMIND AI",
    description=(
        "FINMIND AI — AI-Powered Financial Intelligence & Business Simulation Platform. "
        "Features: Schema-free file ingestion, trained ML categorization (TF-IDF + LR), "
        "Isolation Forest anomaly detection, statistical cash-flow forecasting, "
        "Business Financial Digital Twin simulator, and evidence-backed AI Copilot."
    ),
    version="2.0.0",
)

# ── CORS ──────────────────────────────────────────────────────
origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
origins = [o.strip() for o in origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(alerts.router)
app.include_router(analytics.router)
app.include_router(ai.router)
app.include_router(reports.router)
app.include_router(ml_router.router)


@app.get("/", tags=["health"])
def root():
    return {
        "service": "FINMIND AI",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "usps": [
            "Schema-Free Financial Intelligence",
            "Trained ML Models (Categorizer + Anomaly Detector)",
            "Statistical Cash-Flow Forecasting",
            "Business Financial Early-Warning System",
            "Business Financial Digital Twin Simulator",
        ],
    }


@app.get("/health", tags=["health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok", "database": "connected"}
