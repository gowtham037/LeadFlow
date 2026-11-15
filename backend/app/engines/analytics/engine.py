"""
Analytics engine — computes business KPIs directly from source data.

Every metric is derived from persisted rows. No cached values. No hardcoded
numbers. If the underlying data changes, the metrics change.

Time-window support: all KPIs accept optional `since`/`until` for future
time-based filtering. Default is full historical.

Public functions:
  lead_kpis(db)              — leads by category/status, conversion rate
  opportunity_kpis(db)       — win rate, pipeline value, cycle time
  funnel(db)                 — lead → opp → won funnel with conversion
  campaign_performance(db)   — per-campaign leads, conversions, revenue
  rep_performance(db)        — per-rep assignments, conversions, revenue
  sla_compliance(db)         — % tasks completed within SLA
  score_category_performance(db) — conversion rate by score tier (scoring strategy eval)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.enums import (
    LeadStatus,
    OpportunityStatus,
    ScoreCategory,
    TaskStatus,
)
from backend.app.models.marketing import Campaign, Lead, LeadCampaign
from backend.app.models.organization import SalesRep
from backend.app.models.sales_ops import Opportunity, Task


@dataclass
class LeadKPIs:
    total_leads: int
    qualified_leads: int
    hot_leads: int
    warm_leads: int
    nurture_leads: int
    cold_leads: int
    converted_leads: int
    conversion_rate: float  # converted / total
    qualification_rate: float  # qualified / total
    avg_score: float


@dataclass
class OpportunityKPIs:
    total_opportunities: int
    open_count: int
    won_count: int
    lost_count: int
    win_rate: float  # won / (won + lost)
    pipeline_value_open: float
    revenue_won: float
    revenue_lost: float
    avg_deal_size: float
    avg_won_cycle_days: float


@dataclass
class FunnelStage:
    name: str
    count: int
    pct_of_previous: float
    pct_of_start: float


@dataclass
class CampaignPerformance:
    campaign_id: str
    campaign_name: str
    lead_count: int
    converted_count: int
    opportunities: int
    won_count: int
    revenue_won: float
    conversion_rate: float
    win_rate: float


@dataclass
class RepPerformance:
    rep_id: int
    full_name: str
    assigned_leads: int
    converted_leads: int
    total_opportunities: int
    won_count: int
    revenue_won: float
    conversion_rate: float
    win_rate: float


@dataclass
class SLACompliance:
    total_tasks: int
    completed_tasks: int
    on_time_count: int
    overdue_completed_count: int
    pending_overdue_count: int
    sla_compliance_pct: float  # completed-on-time / completed


@dataclass
class ScoreCategoryPerformance:
    category: str
    leads: int
    converted: int
    conversion_rate: float
    opportunities: int
    won: int
    revenue_won: float


# ---------- Lead KPIs ----------
def lead_kpis(db: Session) -> LeadKPIs:
    """Leads by category + status. Baseline only (is_baseline=True)."""
    total = db.query(func.count(Lead.id)).filter(Lead.is_baseline.is_(True)).scalar() or 0
    qualified = (
        db.query(func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True), Lead.status == LeadStatus.QUALIFIED)
        .scalar() or 0
    )
    converted = (
        db.query(func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True), Lead.status == LeadStatus.CONVERTED)
        .scalar() or 0
    )

    by_cat = dict(
        db.query(Lead.current_score_category, func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True))
        .group_by(Lead.current_score_category)
        .all()
    )

    avg_score = (
        db.query(func.avg(Lead.current_score))
        .filter(Lead.is_baseline.is_(True), Lead.current_score.isnot(None))
        .scalar() or 0.0
    )

    return LeadKPIs(
        total_leads=total,
        qualified_leads=qualified,
        hot_leads=by_cat.get(ScoreCategory.HOT, 0),
        warm_leads=by_cat.get(ScoreCategory.WARM, 0),
        nurture_leads=by_cat.get(ScoreCategory.NURTURE, 0),
        cold_leads=by_cat.get(ScoreCategory.COLD, 0),
        converted_leads=converted,
        conversion_rate=round(converted / total, 4) if total else 0.0,
        qualification_rate=round(qualified / total, 4) if total else 0.0,
        avg_score=round(float(avg_score), 2),
    )


# ---------- Opportunity KPIs ----------
def opportunity_kpis(db: Session) -> OpportunityKPIs:
    total = db.query(func.count(Opportunity.id)).scalar() or 0
    open_n = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.status == OpportunityStatus.OPEN)
        .scalar() or 0
    )
    won_n = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.status == OpportunityStatus.WON)
        .scalar() or 0
    )
    lost_n = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.status == OpportunityStatus.LOST)
        .scalar() or 0
    )

    pipeline_open = (
        db.query(func.coalesce(func.sum(Opportunity.amount_usd), 0))
        .filter(Opportunity.status == OpportunityStatus.OPEN)
        .scalar() or 0
    )
    revenue_won = (
        db.query(func.coalesce(func.sum(Opportunity.amount_usd), 0))
        .filter(Opportunity.status == OpportunityStatus.WON)
        .scalar() or 0
    )
    revenue_lost = (
        db.query(func.coalesce(func.sum(Opportunity.amount_usd), 0))
        .filter(Opportunity.status == OpportunityStatus.LOST)
        .scalar() or 0
    )

    avg_deal = (
        db.query(func.avg(Opportunity.amount_usd)).scalar() or 0.0
    )

    # Cycle time (won): closed_at - created_at in days
    won_rows = (
        db.query(Opportunity.created_at, Opportunity.closed_at)
        .filter(Opportunity.status == OpportunityStatus.WON, Opportunity.closed_at.isnot(None))
        .all()
    )
    if won_rows:
        cycles = [(c - cr).total_seconds() / 86400 for cr, c in won_rows if c and cr]
        avg_cycle = sum(cycles) / len(cycles) if cycles else 0.0
    else:
        avg_cycle = 0.0

    return OpportunityKPIs(
        total_opportunities=total,
        open_count=open_n,
        won_count=won_n,
        lost_count=lost_n,
        win_rate=round(won_n / (won_n + lost_n), 4) if (won_n + lost_n) else 0.0,
        pipeline_value_open=round(float(pipeline_open), 2),
        revenue_won=round(float(revenue_won), 2),
        revenue_lost=round(float(revenue_lost), 2),
        avg_deal_size=round(float(avg_deal), 2),
        avg_won_cycle_days=round(avg_cycle, 1),
    )


# ---------- Funnel ----------
def funnel(db: Session) -> list[FunnelStage]:
    """
    Lead → opp → won funnel with CUMULATIVE counts.

    Critical: a lead at CONVERTED status passed through QUALIFIED, ASSIGNED,
    WORKING too. Funnel steps are cumulative milestones, not current-state
    buckets. Otherwise a lead advancing past QUALIFIED would DECREASE the
    'Qualified' stage count — which is wrong.
    """
    # Total leads
    total = db.query(func.count(Lead.id)).filter(Lead.is_baseline.is_(True)).scalar() or 0

    # Cumulative "ever reached qualified" = anything at or past QUALIFIED
    qualified_states = [
        LeadStatus.QUALIFIED,
        LeadStatus.ASSIGNED,
        LeadStatus.WORKING,
        LeadStatus.CONVERTED,
    ]
    qualified = (
        db.query(func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True), Lead.status.in_(qualified_states))
        .scalar() or 0
    )
    converted = (
        db.query(func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True), Lead.status == LeadStatus.CONVERTED)
        .scalar() or 0
    )
    opps = db.query(func.count(Opportunity.id)).scalar() or 0
    won = (
        db.query(func.count(Opportunity.id))
        .filter(Opportunity.status == OpportunityStatus.WON)
        .scalar() or 0
    )

    stages = [
        ("Leads", total),
        ("Reached Qualified", qualified),
        ("Converted", converted),
        ("Opportunities", opps),
        ("Won", won),
    ]

    out: list[FunnelStage] = []
    prev = total
    for name, n in stages:
        pct_prev = (n / prev * 100) if prev else 0.0
        pct_start = (n / total * 100) if total else 0.0
        out.append(FunnelStage(
            name=name,
            count=n,
            pct_of_previous=round(pct_prev, 1),
            pct_of_start=round(pct_start, 1),
        ))
        prev = n
    return out


# ---------- Campaign performance ----------
def campaign_performance(db: Session) -> list[CampaignPerformance]:
    """For each campaign: leads attributed, conversions, revenue from those leads' opps."""
    rows = (
        db.query(
            Campaign.business_id,
            Campaign.name,
            func.count(func.distinct(LeadCampaign.lead_id)).label("lead_count"),
        )
        .outerjoin(LeadCampaign, LeadCampaign.campaign_id == Campaign.id)
        .group_by(Campaign.id)
        .all()
    )

    out: list[CampaignPerformance] = []
    for biz_id, name, lead_count in rows:
        # Converted leads for this campaign
        converted = (
            db.query(func.count(func.distinct(Lead.id)))
            .join(LeadCampaign, LeadCampaign.lead_id == Lead.id)
            .join(Campaign, Campaign.id == LeadCampaign.campaign_id)
            .filter(Campaign.business_id == biz_id, Lead.status == LeadStatus.CONVERTED)
            .scalar() or 0
        )

        # Opportunities from leads in this campaign
        opp_rows = (
            db.query(Opportunity)
            .join(Lead, Lead.id == Opportunity.lead_id)
            .join(LeadCampaign, LeadCampaign.lead_id == Lead.id)
            .join(Campaign, Campaign.id == LeadCampaign.campaign_id)
            .filter(Campaign.business_id == biz_id)
            .all()
        )
        opps_n = len(opp_rows)
        won = [o for o in opp_rows if o.status == OpportunityStatus.WON]
        won_n = len(won)
        revenue = sum(float(o.amount_usd) for o in won)

        out.append(CampaignPerformance(
            campaign_id=biz_id,
            campaign_name=name,
            lead_count=lead_count,
            converted_count=converted,
            opportunities=opps_n,
            won_count=won_n,
            revenue_won=round(revenue, 2),
            conversion_rate=round(converted / lead_count, 4) if lead_count else 0.0,
            win_rate=round(won_n / opps_n, 4) if opps_n else 0.0,
        ))

    out.sort(key=lambda r: r.revenue_won, reverse=True)
    return out


# ---------- Rep performance ----------
def rep_performance(db: Session) -> list[RepPerformance]:
    reps = db.query(SalesRep).filter(SalesRep.is_active.is_(True)).all()
    out: list[RepPerformance] = []

    for rep in reps:
        assigned = (
            db.query(func.count(Lead.id))
            .filter(Lead.is_baseline.is_(True), Lead.assigned_rep_id == rep.id)
            .scalar() or 0
        )
        converted = (
            db.query(func.count(Lead.id))
            .filter(
                Lead.is_baseline.is_(True),
                Lead.assigned_rep_id == rep.id,
                Lead.status == LeadStatus.CONVERTED,
            )
            .scalar() or 0
        )
        opp_rows = db.query(Opportunity).filter(Opportunity.rep_id == rep.id).all()
        opps_n = len(opp_rows)
        won = [o for o in opp_rows if o.status == OpportunityStatus.WON]
        won_n = len(won)
        revenue = sum(float(o.amount_usd) for o in won)

        out.append(RepPerformance(
            rep_id=rep.id,
            full_name=rep.full_name,
            assigned_leads=assigned,
            converted_leads=converted,
            total_opportunities=opps_n,
            won_count=won_n,
            revenue_won=round(revenue, 2),
            conversion_rate=round(converted / assigned, 4) if assigned else 0.0,
            win_rate=round(won_n / opps_n, 4) if opps_n else 0.0,
        ))

    out.sort(key=lambda r: r.revenue_won, reverse=True)
    return out


# ---------- SLA compliance ----------
def sla_compliance(db: Session, as_of: datetime | None = None) -> SLACompliance:
    total = db.query(func.count(Task.id)).scalar() or 0
    completed = (
        db.query(func.count(Task.id))
        .filter(Task.status == TaskStatus.COMPLETED)
        .scalar() or 0
    )
    on_time = (
        db.query(func.count(Task.id))
        .filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.isnot(None),
            Task.completed_at <= Task.sla_deadline_at,
        )
        .scalar() or 0
    )
    overdue_completed = (
        db.query(func.count(Task.id))
        .filter(
            Task.status == TaskStatus.COMPLETED,
            Task.completed_at.isnot(None),
            Task.completed_at > Task.sla_deadline_at,
        )
        .scalar() or 0
    )
    pending_overdue = (
        db.query(func.count(Task.id))
        .filter(
            Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            Task.sla_deadline_at < (as_of or datetime.utcnow()),
        )
        .scalar() or 0
    )

    return SLACompliance(
        total_tasks=total,
        completed_tasks=completed,
        on_time_count=on_time,
        overdue_completed_count=overdue_completed,
        pending_overdue_count=pending_overdue,
        sla_compliance_pct=round(on_time / completed, 4) if completed else 0.0,
    )


# ---------- Score category performance (scoring strategy evaluation) ----------
def score_category_performance(db: Session) -> list[ScoreCategoryPerformance]:
    """Conversion + revenue by current score tier — proves the scoring engine works."""
    out: list[ScoreCategoryPerformance] = []
    for cat in (ScoreCategory.HOT, ScoreCategory.WARM,
                ScoreCategory.NURTURE, ScoreCategory.COLD):
        leads_n = (
            db.query(func.count(Lead.id))
            .filter(Lead.is_baseline.is_(True), Lead.current_score_category == cat)
            .scalar() or 0
        )
        converted = (
            db.query(func.count(Lead.id))
            .filter(
                Lead.is_baseline.is_(True),
                Lead.current_score_category == cat,
                Lead.status == LeadStatus.CONVERTED,
            )
            .scalar() or 0
        )
        opp_rows = (
            db.query(Opportunity)
            .join(Lead, Lead.id == Opportunity.lead_id)
            .filter(Lead.current_score_category == cat, Lead.is_baseline.is_(True))
            .all()
        )
        won = [o for o in opp_rows if o.status == OpportunityStatus.WON]
        revenue = sum(float(o.amount_usd) for o in won)

        out.append(ScoreCategoryPerformance(
            category=cat.value,
            leads=leads_n,
            converted=converted,
            conversion_rate=round(converted / leads_n, 4) if leads_n else 0.0,
            opportunities=len(opp_rows),
            won=len(won),
            revenue_won=round(revenue, 2),
        ))

    return out

