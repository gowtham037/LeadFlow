"""
Batch opportunity runner — converts CONVERTED-status leads that lack an opportunity.

Idempotent: skips leads that already have an opportunity.
Deterministic: iterates by lead.id ascending.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.engines.opportunity.engine import (
    DuplicateOpportunity,
    create_opportunity,
)
from backend.app.models.enums import LeadStatus
from backend.app.models.marketing import Lead
from backend.app.models.sales_ops import Opportunity

logger = logging.getLogger("opportunity.runner")


def convert_all_eligible_leads(db: Session, limit: int | None = None) -> dict:
    """
    Create opportunities for every CONVERTED lead that doesn't already have one.
    """
    now = datetime.now(timezone.utc)

    already_have_opp = {row[0] for row in db.query(Opportunity.lead_id).all()}

    leads = (
        db.query(Lead)
        .filter(
            Lead.is_baseline.is_(True),
            Lead.status == LeadStatus.CONVERTED,
            Lead.assigned_rep_id.isnot(None),
        )
        .order_by(Lead.id.asc())
        .all()
    )

    logger.info("Evaluating %d converted leads for opportunity creation", len(leads))

    summary = Counter()
    created = 0
    for lead in leads:
        if lead.id in already_have_opp:
            summary["skipped_already_has_opp"] += 1
            continue

        try:
            create_opportunity(db, lead, as_of=now)
            summary["created"] += 1
            created += 1
        except DuplicateOpportunity:
            summary["skipped_already_has_opp"] += 1
        except ValueError as exc:
            summary["skipped_invalid"] += 1
            logger.debug("skip lead %d: %s", lead.id, exc)

        if created > 0 and created % 200 == 0:
            logger.info("  created %d opportunities so far", created)
            db.commit()

    db.commit()
    logger.info("Opportunity conversion complete: %d opportunities created", created)
    return dict(summary)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    try:
        summary = convert_all_eligible_leads(db)
        print("\n=== OPPORTUNITY CONVERSION SUMMARY ===")
        for k, v in sorted(summary.items()):
            print(f"  {k:35s} {v}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())
