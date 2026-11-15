"""
Batch task runner — creates follow-up tasks for all eligible assigned leads.

Idempotent: skips leads that already have an open task.
Deterministic: iterates leads by id ascending.
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.engines.task_management.engine import create_followup_task
from backend.app.models.enums import LeadStatus, ScoreCategory, TaskStatus
from backend.app.models.marketing import Lead
from backend.app.models.sales_ops import Task

logger = logging.getLogger("task_management.runner")


def generate_all_followup_tasks(db: Session, limit: int | None = None) -> dict:
    """
    Create tasks for every eligible assigned lead that doesn't already have
    an open task.
    """
    now = datetime.now(timezone.utc)

    # Leads with an assigned rep, in a state that warrants a task
    leads = (
        db.query(Lead)
        .filter(
            Lead.is_baseline.is_(True),
            Lead.assigned_rep_id.isnot(None),
            Lead.status.in_([LeadStatus.QUALIFIED, LeadStatus.ASSIGNED, LeadStatus.WORKING]),
        )
        .order_by(Lead.id.asc())
        .all()
    )

    logger.info("Evaluating %d assigned leads for task creation", len(leads))

    # Leads that already have an open task (idempotency)
    existing_open = {
        task.lead_id
        for task in db.query(Task)
        .filter(Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]))
        .all()
    }

    summary = Counter()
    created = 0
    for lead in leads:
        summary[f"lead_category_{lead.current_score_category.value if lead.current_score_category else 'none'}"] += 1

        if lead.id in existing_open:
            summary["skipped_already_has_open_task"] += 1
            continue

        task = create_followup_task(db, lead, as_of=now)
        if task is None:
            summary["skipped_not_eligible"] += 1
            continue

        summary[f"created_{task.priority.value}"] += 1
        summary["created"] += 1
        created += 1

        if created % 200 == 0:
            logger.info("  created %d tasks so far", created)
            db.commit()

    db.commit()
    logger.info("Task generation complete: %d tasks created", created)
    return dict(summary)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    try:
        summary = generate_all_followup_tasks(db)
        print("\n=== TASK GENERATION SUMMARY ===")
        for k, v in sorted(summary.items()):
            print(f"  {k:35s} {v}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())

