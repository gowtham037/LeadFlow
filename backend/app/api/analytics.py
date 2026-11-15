"""
Analytics endpoints — all KPIs computed from source data.

GET /api/analytics/lead-kpis
GET /api/analytics/opportunity-kpis
GET /api/analytics/funnel
GET /api/analytics/campaign-performance
GET /api/analytics/rep-performance
GET /api/analytics/sla-compliance
GET /api/analytics/score-category-performance
GET /api/analytics/dashboard          — one call returns all KPIs (dashboard)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.engines.analytics import (
    campaign_performance,
    funnel,
    lead_kpis,
    opportunity_kpis,
    rep_performance,
    score_category_performance,
    sla_compliance,
)
from backend.app.models.system import User


router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _ser(obj):
    """Convert a dataclass to a dict."""
    return obj.__dict__ if hasattr(obj, "__dict__") else obj


@router.get("/lead-kpis")
def get_lead_kpis(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> dict:
    return _ser(lead_kpis(db))


@router.get("/opportunity-kpis")
def get_opp_kpis(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> dict:
    return _ser(opportunity_kpis(db))


@router.get("/funnel")
def get_funnel(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list:
    return [_ser(s) for s in funnel(db)]


@router.get("/campaign-performance")
def get_campaign_perf(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list:
    return [_ser(s) for s in campaign_performance(db)]


@router.get("/rep-performance")
def get_rep_perf(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list:
    return [_ser(s) for s in rep_performance(db)]


@router.get("/sla-compliance")
def get_sla(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> dict:
    return _ser(sla_compliance(db))


@router.get("/score-category-performance")
def get_score_perf(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> list:
    return [_ser(s) for s in score_category_performance(db)]


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db), _u: User = Depends(get_current_user)) -> dict:
    """One-call aggregate for the executive dashboard."""
    return {
        "leads": _ser(lead_kpis(db)),
        "opportunities": _ser(opportunity_kpis(db)),
        "funnel": [_ser(s) for s in funnel(db)],
        "score_categories": [_ser(s) for s in score_category_performance(db)],
        "sla": _ser(sla_compliance(db)),
        "top_campaigns": [_ser(c) for c in campaign_performance(db)[:5]],
        "top_reps": [_ser(r) for r in rep_performance(db)[:5]],
    }
