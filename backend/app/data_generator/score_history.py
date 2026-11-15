"""
Score history generator — one LeadScoreHistory row per lead.

The history table is IMMUTABLE. Each row snapshots:
- Component scores (fit, intent, engagement, recency)
- Total + category
- Contributions_json (feature-level breakdown for the UI)
- Input cutoff (what data the scorer was allowed to see)

This mirrors what the real scoring engine will write once it runs.
"""
from __future__ import annotations

import json
from datetime import timedelta

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.models.enums import LeadStatus, ScoreCategory
from backend.app.models.marketing import Lead
from backend.app.models.scoring import LeadScoreHistory, ScoreRule


def _breakdown(fake: Faker, rule: ScoreRule, target_total: int) -> dict:
    """
    Deterministic decomposition of target_total into 4 components weighted
    by the rule (30/35/25/10).
    """
    weights = {
        "fit": rule.fit_weight,
        "intent": rule.intent_weight,
        "engagement": rule.engagement_weight,
        "recency": rule.recency_weight,
    }
    components = {}
    allocated = 0
    for i, (name, w) in enumerate(weights.items()):
        max_pts = w  # each component max = its weight
        if i == len(weights) - 1:
            # last component gets remainder so sum matches exactly
            remaining = target_total - allocated
            val = max(0, min(max_pts, remaining))
        else:
            # scale: how much of this weight did the lead achieve?
            share = target_total / 100.0
            base = int(round(w * share))
            jitter = fake.random_int(min=-2, max=2)
            val = max(0, min(max_pts, base + jitter))
        components[name] = val
        allocated += val
    return components


def generate_score_history(
    db: Session,
    leads: list[Lead],
    rule: ScoreRule,
    seed: int,
) -> list[LeadScoreHistory]:
    fake = Faker()
    Faker.seed(seed + 6)

    rows: list[LeadScoreHistory] = []
    for lead in leads:
        cat = lead.current_score_category or ScoreCategory.COLD
        total = lead.current_score or 0

        # Decompose total using rule weights
        parts = _breakdown(fake, rule, total)
        fit = parts["fit"]
        intent = parts["intent"]
        engagement = parts["engagement"]
        recency = parts["recency"]
        # Adjust: ensure sum == total after clamping
        diff = total - (fit + intent + engagement + recency)
        if diff != 0:
            # nudge fit by diff while staying in bounds
            fit = max(0, min(rule.fit_weight, fit + diff))
            # if still off, nudge intent
            diff2 = total - (fit + intent + engagement + recency)
            intent = max(0, min(rule.intent_weight, intent + diff2))
            # if still off, nudge engagement
            diff3 = total - (fit + intent + engagement + recency)
            engagement = max(0, min(rule.engagement_weight, engagement + diff3))

        scored_at = lead.last_scored_at or lead.created_at
        contributions = [
            {
                "feature": "fit",
                "value": fit,
                "weight": rule.fit_weight,
                "explanation": f"Company fit score: {fit}/{rule.fit_weight}",
            },
            {
                "feature": "intent",
                "value": intent,
                "weight": rule.intent_weight,
                "explanation": f"Purchase intent: {intent}/{rule.intent_weight}",
            },
            {
                "feature": "engagement",
                "value": engagement,
                "weight": rule.engagement_weight,
                "explanation": f"Engagement signal: {engagement}/{rule.engagement_weight}",
            },
            {
                "feature": "recency",
                "value": recency,
                "weight": rule.recency_weight,
                "explanation": f"Recency of activity: {recency}/{rule.recency_weight}",
            },
        ]

        rows.append(
            LeadScoreHistory(
                lead_id=lead.id,
                rule_version=rule.version,
                input_cutoff_at=scored_at,
                scored_at=scored_at,
                fit_score=fit,
                intent_score=intent,
                engagement_score=engagement,
                recency_score=recency,
                total_score=total,
                score_category=cat,
                contributions_json=json.dumps(contributions),
            )
        )

    db.add_all(rows)
    db.flush()
    return rows

