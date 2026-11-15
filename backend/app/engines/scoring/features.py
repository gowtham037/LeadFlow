"""
Feature extraction for the scoring engine.

PURE — takes a lead_id + cutoff timestamp, returns a Features object.
Never mutates DB. Never touches ground truth. Only reads rows where
occurred_at <= cutoff (for activities) and changed_at <= cutoff (consents).

Scoring inputs are split into 4 categories:
  Fit        (30) — company characteristics + territory match
  Intent     (35) — high-value activities (demo, meeting, content)
  Engagement (25) — broad engagement (opens, clicks, visits)
  Recency    (10) — days since last activity
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.enums import ActivityType, ConsentChannel, ConsentStatus
from backend.app.models.marketing import Activity, Consent, Lead
from backend.app.models.organization import Company


@dataclass
class Features:
    """Raw features extracted from DB for one lead at one cutoff."""

    lead_id: int

    # Fit inputs
    employee_count: int = 0
    annual_revenue_usd: float = 0.0
    industry: str = ""
    company_territory_id: int | None = None
    lead_territory_id: int | None = None
    territory_match: bool = False

    # Intent inputs
    demo_requests: int = 0
    meetings: int = 0
    content_downloads: int = 0
    calls: int = 0

    # Engagement inputs
    email_opens: int = 0
    email_clicks: int = 0
    web_visits: int = 0
    total_activities: int = 0

    # Recency inputs
    days_since_last_activity: int = 9999  # large default if no activity

    # Consent snapshot (used to block outbound tasks, not for scoring)
    consent_email: ConsentStatus | None = None
    consent_phone: ConsentStatus | None = None

    # Diagnostic
    cutoff_at: datetime | None = None
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def extract_features(db: Session, lead_id: int, cutoff_at: datetime) -> Features:
    """
    Extract features for one lead at a specific cutoff timestamp.

    CRITICAL: only activities with occurred_at <= cutoff_at are counted.
    This prevents post-conversion events from affecting pre-conversion scores.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).one_or_none()
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")

    company = db.query(Company).filter(Company.id == lead.company_id).one_or_none()
    if company is None:
        raise ValueError(f"Company {lead.company_id} for lead {lead_id} not found")

    f = Features(lead_id=lead_id, cutoff_at=cutoff_at)
    f.employee_count = company.employee_count
    f.annual_revenue_usd = float(company.annual_revenue_usd)
    f.industry = company.industry
    f.company_territory_id = company.territory_id
    f.lead_territory_id = lead.territory_id
    f.territory_match = (company.territory_id == lead.territory_id)

    # Activity breakdown by type, respecting cutoff
    activity_q = (
        db.query(Activity.activity_type, func.count(Activity.id))
        .filter(Activity.lead_id == lead_id, Activity.occurred_at <= cutoff_at)
        .group_by(Activity.activity_type)
    )
    counts: dict[ActivityType, int] = {row[0]: row[1] for row in activity_q.all()}

    f.demo_requests = counts.get(ActivityType.DEMO_REQUEST, 0)
    f.meetings = counts.get(ActivityType.MEETING, 0)
    f.content_downloads = counts.get(ActivityType.CONTENT_DOWNLOAD, 0)
    f.calls = counts.get(ActivityType.CALL, 0)
    f.email_opens = counts.get(ActivityType.EMAIL_OPEN, 0)
    f.email_clicks = counts.get(ActivityType.EMAIL_CLICK, 0)
    f.web_visits = counts.get(ActivityType.WEB_VISIT, 0)
    f.total_activities = sum(counts.values())

    # Recency — days since last activity <= cutoff
    last_activity = (
        db.query(func.max(Activity.occurred_at))
        .filter(Activity.lead_id == lead_id, Activity.occurred_at <= cutoff_at)
        .scalar()
    )
    if last_activity is not None:
        delta = cutoff_at - last_activity
        f.days_since_last_activity = max(0, int(delta.total_seconds() // 86400))

    # Consent snapshot at cutoff (latest row per channel with changed_at <= cutoff)
    for channel in (ConsentChannel.EMAIL, ConsentChannel.PHONE):
        row = (
            db.query(Consent)
            .filter(
                Consent.lead_id == lead_id,
                Consent.channel == channel,
                Consent.changed_at <= cutoff_at,
            )
            .order_by(Consent.changed_at.desc())
            .first()
        )
        if row is not None:
            if channel == ConsentChannel.EMAIL:
                f.consent_email = row.status
            else:
                f.consent_phone = row.status

    return f
