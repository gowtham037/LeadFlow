"""
Orchestrator — runs the full synthetic data generation in topological order.

Steps:
  1. Wipe all business tables (keep schema + extensions).
  2. Reset ID sequences.
  3. Master data → companies → contacts → score rule → leads → activities →
     consents → score history → assignments → tasks → opportunities →
     anomalies.
  4. Print per-table row counts.
  5. Write SHA-256 of ground_truth.csv for reproducibility auditing.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.data_generator.activities import generate_activities
from backend.app.data_generator.assignments import generate_assignment_history
from backend.app.data_generator.companies_contacts import (
    generate_companies,
    generate_contacts,
)
from backend.app.data_generator.consents import generate_consents
from backend.app.data_generator.edge_cases import GROUND_TRUTH_PATH, inject_anomalies
from backend.app.data_generator.ids import reset_all
from backend.app.data_generator.leads import generate_leads
from backend.app.data_generator.master import generate_master_data
from backend.app.data_generator.opportunities import generate_opportunities
from backend.app.data_generator.score_history import generate_score_history
from backend.app.data_generator.score_rules import generate_score_rules
from backend.app.data_generator.tasks import generate_tasks
from backend.app.database import SessionLocal
from backend.app.models.marketing import (
    Activity, Campaign, Consent, Lead, LeadCampaign,
)
from backend.app.models.organization import (
    Company, Contact, Product, SalesRep, Territory,
)
from backend.app.models.scoring import LeadScoreHistory, ScoreRule
from backend.app.models.sales_ops import (
    DuplicateGroup, LeadAssignmentHistory, Opportunity, StageHistory, Task,
)
from backend.app.models.system import AuditLog, ExceptionRecord, Role, User

logger = logging.getLogger("data_generator")


# Tables to wipe, child-first (FK-safe order)
_WIPE_ORDER = [
    StageHistory, Opportunity, LeadAssignmentHistory, Task, LeadScoreHistory,
    Activity, Consent, LeadCampaign, Lead, DuplicateGroup, ExceptionRecord,
    AuditLog, Campaign, Contact, Company, SalesRep, Product, Territory,
    ScoreRule, User, Role,
]


def wipe_tables(db: Session) -> None:
    logger.info("Wiping business tables...")
    for model in _WIPE_ORDER:
        db.query(model).delete()
    db.commit()


def row_counts(db: Session) -> dict[str, int]:
    counts = {}
    for model in [
        Role, User, Territory, Product, SalesRep, Campaign, Company, Contact,
        Lead, LeadCampaign, Activity, Consent, ScoreRule, LeadScoreHistory,
        LeadAssignmentHistory, Task, Opportunity, StageHistory, DuplicateGroup,
        ExceptionRecord, AuditLog,
    ]:
        counts[model.__tablename__] = db.query(model).count()
    return counts


def sha256_of(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def run(mode: str = "full", seed: int = cfg.DEFAULT_SEED) -> dict[str, int]:
    volumes = cfg.STARTER_VOLUMES if mode == "starter" else cfg.FULL_VOLUMES

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    db = SessionLocal()
    try:
        wipe_tables(db)
        reset_all()

        logger.info("Generating master data...")
        master = generate_master_data(db, seed, volumes)
        territories = master["territories"]
        products = master["products"]
        reps = master["sales_reps"]
        campaigns = master["campaigns"]

        logger.info("Generating companies...")
        companies = generate_companies(db, territories, seed, volumes.companies)

        logger.info("Generating contacts...")
        contacts = generate_contacts(db, companies, seed, volumes.contacts)

        logger.info("Generating score rule v1...")
        rule = generate_score_rules(db)

        logger.info("Generating leads...")
        leads = generate_leads(
            db, companies, contacts, territories, products, reps, campaigns,
            seed, volumes.leads,
        )

        logger.info("Generating activities...")
        generate_activities(
            db, leads, seed,
            min_per_lead=volumes.activities_per_lead_min,
            max_per_lead=volumes.activities_per_lead_max,
        )

        logger.info("Generating consents...")
        generate_consents(db, leads, seed)

        logger.info("Generating score history...")
        generate_score_history(db, leads, rule, seed)

        logger.info("Generating assignment history...")
        generate_assignment_history(db, leads, reps, products, seed)

        logger.info("Generating tasks...")
        generate_tasks(db, leads, seed)

        logger.info("Generating opportunities...")
        generate_opportunities(db, leads, products, reps, seed, volumes.opportunities)

        logger.info("Injecting anomalies (5 mandatory scenarios)...")
        inject_anomalies(db, companies, contacts, products, reps, seed)

        db.commit()

        counts = row_counts(db)
        logger.info("=" * 60)
        logger.info("DATA GENERATION COMPLETE (mode=%s, seed=%d)", mode, seed)
        logger.info("=" * 60)
        for table, n in counts.items():
            logger.info(f"  {table:30s} {n:>8d}")

        logger.info("Ground truth: %s", GROUND_TRUTH_PATH)
        logger.info("Ground truth SHA-256: %s", sha256_of(GROUND_TRUTH_PATH))
        logger.info("=" * 60)
        return counts
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LeadFlow synthetic data generator")
    parser.add_argument("--mode", choices=["starter", "full"], default="full")
    parser.add_argument("--seed", type=int, default=cfg.DEFAULT_SEED)
    args = parser.parse_args(argv)
    try:
        run(mode=args.mode, seed=args.seed)
        return 0
    except Exception:
        logger.exception("Generation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
