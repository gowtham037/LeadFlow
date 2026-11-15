"""
LeadFlow FastAPI application entry point.

Mounts:
  - /api/auth           — login, refresh, me
  - /api/leads          — lead list/detail/summary
  - /api/opportunities  — opportunity pipeline
  - /api/analytics      — all KPIs
  - /api/exceptions     — anomaly management
  - /api/admin          — engine triggers, validation
  - /health             — liveness + DB connectivity
  - /docs, /redoc       — Swagger UI

CORS allows the frontend at http://localhost:3001 and http://localhost:5173.
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.config import settings
from backend.app.database import Base, engine
from backend.app.models import *  # noqa: F401,F403  — registers all models


logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{settings.frontend_port}",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting %s (env=%s)", settings.app_name, settings.environment)

    # Enable required PostgreSQL extensions (idempotent)
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        conn.commit()

    # Create tables idempotently (no-op if Alembic already created them)
    Base.metadata.create_all(bind=engine)
    logger.info("Schema ensured. Tables: %s", ", ".join(sorted(Base.metadata.tables)))


# Mount all API routes
app.include_router(api_router)


# ---------- Root + health ----------

@app.get("/health", tags=["health"])
def health() -> dict:
    """Liveness + DB connectivity probe."""
    from sqlalchemy import text
    from backend.app.database import SessionLocal
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok", "env": settings.environment}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Health check failed")
        return {"status": "degraded", "database": "unreachable", "error": str(exc)}


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/*",
    }