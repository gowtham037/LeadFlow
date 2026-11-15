"""
Batch routing runner — routes all QUALIFIED, unassigned leads.

Called by:
  - API (`POST /api/admin/route-leads`)
  - CLI: `python -m backend.app.engines.routing.runner`

Guarantees:
  - Idempotent: only touches leads with status=QUALIFIED and assigned_rep_id IS NULL
  - Deterministic: same lead order → same assignments
  - Transactional: each lead's assignment + rep workload + history commit atomically
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.engines.routing.engine import apply_decision, route_lead
from backend.app.models.enums import AssignmentReason, LeadStatus
from backend.app.models.marketing import Lead

logger = logging.getLogger("routing.runner")


def route_all_qualified_leads(db: Session, limit: int | None = None) -> dict:
    """
    Route all leads with status=QUALIFIED and assigned_rep_id IS NULL.
    Returns summary counts.
    """
    q = (
        db.query(Lead)
        .filter(
            Lead.is_baseline.is_(True),
            Lead.status == LeadStatus.QUALIFIED,
            Lead.assigned_rep_id.is_(None),
        )
        .order_by(Lead.id.asc())  # deterministic order
    )
    if limit:
        q = q.limit(limit)
    leads = q.all()

    logger.info("Routing %d qualified leads", len(leads))

    summary = Counter()
    processed = 0
    for lead in leads:
        decision = route_lead(lead, db)
        if decision.assigned:
            apply_decision(decision, lead, db)
            summary[decision.reason.value] += 1
            summary["assigned"] += 1
        else:
            summary["unroutable"] += 1

        processed += 1
        if processed % 200 == 0:
            logger.info("  processed %d/%d — assigned=%d, unroutable=%d",
                        processed, len(leads),
                        summary["assigned"], summary["unroutable"])
            db.commit()

    db.commit()
    logger.info("Routing complete: %d leads", len(leads))
    return dict(summary)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    try:
        summary = route_all_qualified_leads(db)
        print("\n=== ROUTING SUMMARY ===")
        for k, v in sorted(summary.items()):
            print(f"  {k:30s} {v}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())

