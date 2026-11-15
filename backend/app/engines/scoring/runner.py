"""
Batch scoring runner — re-scores leads and writes to lead_score_history.

Called by:
  - The API (`POST /api/admin/rescore`)
  - Manual CLI: `python -m backend.app.engines.scoring.runner`
  - Future background jobs

For each lead:
  1. Determine cutoff (default = last_scored_at or created_at, or now for re-score)
  2. Extract features at cutoff
  3. Run engine
  4. Write LeadScoreHistory row (IMMUTABLE)
  5. Update denormalized fields on Lead (current_score, current_score_category, ...)

Guarantees:
  - Never modifies ground truth
  - Never scores a lead using post-cutoff activities
  - Writes one immutable history row per lead per call (append-only)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.engines.scoring.engine import calculate_score
from backend.app.engines.scoring.features import extract_features
from backend.app.models.marketing import Lead
from backend.app.models.scoring import LeadScoreHistory, ScoreRule

logger = logging.getLogger("scoring.runner")


def _pick_active_rule(db: Session) -> ScoreRule:
    rule = (
        db.query(ScoreRule)
        .filter(ScoreRule.is_active.is_(True))
        .order_by(ScoreRule.id.desc())
        .first()
    )
    if rule is None:
        raise RuntimeError("No active ScoreRule — run `./run-local.sh seed starter` first")
    return rule


def rescore_lead(
    db: Session,
    lead: Lead,
    rule: ScoreRule,
    cutoff_at: datetime | None = None,
) -> LeadScoreHistory:
    """Re-score one lead at the given cutoff (default: now) and persist."""
    cutoff = cutoff_at or datetime.now(timezone.utc)

    features = extract_features(db, lead.id, cutoff)
    result = calculate_score(features, rule)

    history = LeadScoreHistory(
        lead_id=lead.id,
        rule_version=rule.version,
        input_cutoff_at=cutoff,
        scored_at=cutoff,
        fit_score=result.fit_score,
        intent_score=result.intent_score,
        engagement_score=result.engagement_score,
        recency_score=result.recency_score,
        total_score=result.total,
        score_category=result.category,
        contributions_json=json.dumps(result.contributions_as_dicts()),
    )
    db.add(history)

    # Update denormalized snapshot on the lead
    lead.current_score = result.total
    lead.current_score_category = result.category
    lead.current_score_version = rule.version
    lead.last_scored_at = cutoff

    return history


def rescore_all_leads(
    db: Session,
    cutoff_at: datetime | None = None,
    limit: int | None = None,
) -> int:
    """
    Re-score all baseline leads (is_baseline=True). Returns number scored.

    Does NOT touch anomaly leads (is_baseline=False) — those are for the
    data-quality / anomaly center.
    """
    rule = _pick_active_rule(db)
    cutoff = cutoff_at or datetime.now(timezone.utc)

    q = db.query(Lead).filter(Lead.is_baseline.is_(True))
    if limit:
        q = q.limit(limit)
    leads = q.all()

    logger.info("Scoring %d leads with rule %s (cutoff=%s)", len(leads), rule.version, cutoff)
    scored = 0
    for lead in leads:
        rescore_lead(db, lead, rule, cutoff)
        scored += 1
        if scored % 1000 == 0:
            logger.info("  scored %d/%d", scored, len(leads))
            db.commit()

    db.commit()
    logger.info("Scoring complete: %d leads", scored)
    return scored


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = SessionLocal()
    try:
        n = rescore_all_leads(db)
        print(f"Scored {n} leads.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    sys.exit(main())

