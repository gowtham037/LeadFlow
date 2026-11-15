"""
Activity generator — category-driven volume.

Higher-score leads get more touchpoints, weighted toward high-intent
activity types (demo, meeting, call). This produces a realistic engagement
curve where HOT leads actually have the activity volume needed to score HOT.

Ranges (activities per lead):
  HOT     12–20  (heavy demo/meeting/call weighting)
  WARM     4–10  (broad mix)
  NURTURE  2–6   (mostly opens/visits)
  COLD     1–3   (opens only)
"""
from __future__ import annotations

from datetime import timedelta

from faker import Faker
from sqlalchemy.orm import Session

from backend.app.data_generator.ids import activity_id
from backend.app.data_generator.utils import weighted_choice
from backend.app.models.enums import ActivityType, ScoreCategory
from backend.app.models.marketing import Activity, Lead


_CATEGORY_ACTIVITY_PROFILE: dict[ScoreCategory, dict] = {
    ScoreCategory.HOT: {
        "count_range": (12, 20),
        "weights": {
            ActivityType.DEMO_REQUEST: 0.25,
            ActivityType.MEETING: 0.20,
            ActivityType.CALL: 0.22,
            ActivityType.EMAIL_CLICK: 0.15,
            ActivityType.EMAIL_OPEN: 0.05,
            ActivityType.WEB_VISIT: 0.08,
            ActivityType.CONTENT_DOWNLOAD: 0.05,
        },
    },
    ScoreCategory.WARM: {
        "count_range": (4, 10),
        "weights": {
            ActivityType.DEMO_REQUEST: 0.06,
            ActivityType.MEETING: 0.06,
            ActivityType.CALL: 0.15,
            ActivityType.EMAIL_CLICK: 0.20,
            ActivityType.EMAIL_OPEN: 0.23,
            ActivityType.WEB_VISIT: 0.20,
            ActivityType.CONTENT_DOWNLOAD: 0.10,
        },
    },
    ScoreCategory.NURTURE: {
        "count_range": (2, 6),
        "weights": {
            ActivityType.DEMO_REQUEST: 0.00,
            ActivityType.MEETING: 0.00,
            ActivityType.CALL: 0.05,
            ActivityType.EMAIL_CLICK: 0.10,
            ActivityType.EMAIL_OPEN: 0.40,
            ActivityType.WEB_VISIT: 0.30,
            ActivityType.CONTENT_DOWNLOAD: 0.15,
        },
    },
    ScoreCategory.COLD: {
        "count_range": (1, 3),
        "weights": {
            ActivityType.DEMO_REQUEST: 0.00,
            ActivityType.MEETING: 0.00,
            ActivityType.CALL: 0.00,
            ActivityType.EMAIL_CLICK: 0.05,
            ActivityType.EMAIL_OPEN: 0.55,
            ActivityType.WEB_VISIT: 0.30,
            ActivityType.CONTENT_DOWNLOAD: 0.10,
        },
    },
}


def generate_activities(
    db: Session,
    leads: list[Lead],
    seed: int,
    min_per_lead: int = 1,
    max_per_lead: int = 20,
) -> list[Activity]:
    """Generate activities driven by each lead's target score category."""
    fake = Faker()
    Faker.seed(seed + 4)

    activities: list[Activity] = []
    for lead in leads:
        cat = lead.current_score_category or ScoreCategory.COLD
        profile = _CATEGORY_ACTIVITY_PROFILE[cat]

        lo, hi = profile["count_range"]
        n = fake.random_int(min=lo, max=hi)

        types = list(profile["weights"].keys())
        weights = list(profile["weights"].values())

        base = lead.created_at
        # Recency spread by category — HOT leads get the freshest activities
        # (this is what real engaged prospects look like)
        if cat == ScoreCategory.HOT:
            max_days_ago = 14
        elif cat == ScoreCategory.WARM:
            max_days_ago = 21
        else:
            max_days_ago = 30

        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)

        for seq in range(1, n + 1):
            atype = weighted_choice(fake, types, weights)
            # Bias recent for HOT: 60% in last 3 days
            if cat == ScoreCategory.HOT and fake.random_int(0, 100) < 60:
                days_ago = fake.random_int(0, 3)
            else:
                days_ago = fake.random_int(0, max_days_ago)
            occurred = now - timedelta(
                days=days_ago,
                hours=fake.random_int(min=0, max=23),
            )
            # Never before lead creation
            if occurred < base:
                occurred = base
            # Never AFTER conversion (post-conversion activity is only for anomaly)
            if lead.converted_at is not None and occurred > lead.converted_at:
                occurred = lead.converted_at - timedelta(
                    hours=fake.random_int(min=1, max=48),
                )
                if occurred < base:
                    occurred = base
            activities.append(
                Activity(
                    business_id=activity_id(lead.business_id, seq),
                    lead_id=lead.id,
                    activity_type=atype,
                    occurred_at=occurred,
                    metadata_json=None,
                )
            )

    db.add_all(activities)
    db.flush()
    return activities
