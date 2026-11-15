"""
Score rules generator — seeds one active ScoreRule v1.

Weights match the spec exactly: Fit 30, Intent 35, Engagement 25, Recency 10.
Thresholds: Hot ≥ 80, Warm ≥ 60, Nurture ≥ 40, Cold < 40.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.data_generator import config as cfg
from backend.app.models.scoring import ScoreRule


def generate_score_rules(db: Session) -> ScoreRule:
    """Idempotent — returns existing v1 if present, otherwise creates."""
    existing = db.query(ScoreRule).filter_by(version="v1").one_or_none()
    if existing:
        return existing

    rule = ScoreRule(
        version=cfg.SCORE_RULE_V1["version"],
        fit_weight=cfg.SCORE_RULE_V1["fit_weight"],
        intent_weight=cfg.SCORE_RULE_V1["intent_weight"],
        engagement_weight=cfg.SCORE_RULE_V1["engagement_weight"],
        recency_weight=cfg.SCORE_RULE_V1["recency_weight"],
        hot_threshold=cfg.SCORE_RULE_V1["hot_threshold"],
        warm_threshold=cfg.SCORE_RULE_V1["warm_threshold"],
        nurture_threshold=cfg.SCORE_RULE_V1["nurture_threshold"],
        is_active=True,
        activated_at=datetime.now(timezone.utc),
        notes="Initial scoring strategy — spec-locked weights.",
    )
    db.add(rule)
    db.commit()
    return rule

