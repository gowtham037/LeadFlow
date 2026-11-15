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

    # Create tables idempotently
    Base.metadata.create_all(bind=engine)
    logger.info("Schema ensured. Tables: %s", ", ".join(sorted(Base.metadata.tables)))

    # AUTO-SEED on first boot if database is empty
    if settings.auto_seed_on_startup:
        try:
            from backend.app.database import SessionLocal
            from backend.app.models.marketing import Lead
            with SessionLocal() as db:
                lead_count = db.query(Lead).count()
                if lead_count == 0:
                    logger.info("Empty database detected — auto-seeding full dataset (seed=%d)...", settings.data_gen_seed)
                    from backend.app.data_generator.generate import run as run_generator
                    counts = run_generator(mode=settings.data_gen_mode, seed=settings.data_gen_seed)
                    logger.info("Auto-seed complete: %d leads generated", counts.get("leads", 0))

                    # Run the full business pipeline so the demo is fully ready on first boot
                    logger.info("Running scoring engine (this takes ~90s)...")
                    from backend.app.engines.scoring.runner import rescore_all_leads
                    rescore_all_leads(db)

                    logger.info("Running routing engine...")
                    from backend.app.engines.routing.runner import route_all_qualified_leads
                    route_all_qualified_leads(db)

                    logger.info("Running task engine...")
                    from backend.app.engines.task_management.runner import generate_all_followup_tasks
                    generate_all_followup_tasks(db)

                    logger.info("Running opportunity engine...")
                    from backend.app.engines.opportunity.runner import convert_all_eligible_leads
                    convert_all_eligible_leads(db)

                    logger.info("FULL PIPELINE COMPLETE — demo ready")
                else:
                    logger.info("Database already seeded (%d leads). Skipping auto-seed.", lead_count)
        except Exception as exc:
            logger.exception("Auto-seed failed (not fatal — server will start): %s", exc)


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