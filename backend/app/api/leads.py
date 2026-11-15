"""
Lead endpoints.

GET  /api/leads                    — list with filters + pagination
GET  /api/leads/{business_id}      — detail with score explanation + history
GET  /api/leads/stats/summary      — aggregated KPIs
"""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db
from backend.app.models.enums import LeadStatus, ScoreCategory
from backend.app.models.marketing import Consent, Lead
from backend.app.models.organization import Company, Contact, SalesRep
from backend.app.models.scoring import LeadScoreHistory
from backend.app.models.sales_ops import LeadAssignmentHistory, Opportunity, Task
from backend.app.models.system import User


router = APIRouter(prefix="/api/leads", tags=["leads"])


# ---------- Response schemas ----------

class LeadListItem(BaseModel):
    id: int
    business_id: str
    company_name: str
    contact_email: str
    source: str
    status: str
    current_score: int | None
    current_score_category: str | None
    assigned_rep_name: str | None
    created_at: str


class LeadListResponse(BaseModel):
    items: list[LeadListItem]
    total: int
    page: int
    page_size: int
    pages: int


class ScoreContribution(BaseModel):
    feature: str
    raw_value: str | int | float | bool
    points: int
    weight_max: int
    explanation: str


class ScoreDetail(BaseModel):
    total: int
    category: str
    fit: int
    intent: int
    engagement: int
    recency: int
    rule_version: str
    scored_at: str
    contributions: list[ScoreContribution]


class ConsentDetail(BaseModel):
    channel: str
    status: str


class LeadDetail(BaseModel):
    id: int
    business_id: str
    source: str
    status: str
    company: dict
    contact: dict
    assigned_rep: dict | None
    territory_id: int
    product_interest: str
    current_score: int | None
    current_score_category: str | None
    created_at: str
    converted_at: str | None
    score_detail: ScoreDetail | None
    consents: list[ConsentDetail]
    tasks_count: int
    opportunity_id: int | None
    assignment_history_count: int


# ---------- Endpoints ----------

@router.get("", response_model=LeadListResponse)
def list_leads(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = Query(None, description="Search business_id, company name, contact email"),
    status: LeadStatus | None = None,
    category: ScoreCategory | None = None,
    source: str | None = None,
    assigned_rep_id: int | None = None,
    sort_by: Literal["id", "score", "created_at"] = "id",
    order: Literal["asc", "desc"] = "desc",
) -> LeadListResponse:
    qry = db.query(Lead).filter(Lead.is_baseline.is_(True))

    if status:
        qry = qry.filter(Lead.status == status)
    if category:
        qry = qry.filter(Lead.current_score_category == category)
    if source:
        qry = qry.filter(Lead.source == source)
    if assigned_rep_id is not None:
        qry = qry.filter(Lead.assigned_rep_id == assigned_rep_id)

    if q:
        like = f"%{q}%"
        qry = (
            qry.join(Company, Company.id == Lead.company_id)
            .join(Contact, Contact.id == Lead.contact_id)
            .filter(
                or_(
                    Lead.business_id.ilike(like),
                    Company.name.ilike(like),
                    Contact.email.ilike(like),
                )
            )
        )

    sort_col = {
        "id": Lead.id,
        "score": Lead.current_score,
        "created_at": Lead.created_at,
    }[sort_by]
    qry = qry.order_by(desc(sort_col) if order == "desc" else sort_col)

    total = qry.count()
    rows = qry.offset((page - 1) * page_size).limit(page_size).all()

    # Enrich
    company_ids = {r.company_id for r in rows}
    contact_ids = {r.contact_id for r in rows}
    rep_ids = {r.assigned_rep_id for r in rows if r.assigned_rep_id}

    companies = {c.id: c for c in db.query(Company).filter(Company.id.in_(company_ids)).all()}
    contacts = {c.id: c for c in db.query(Contact).filter(Contact.id.in_(contact_ids)).all()}
    reps = {r.id: r for r in db.query(SalesRep).filter(SalesRep.id.in_(rep_ids)).all()}

    items = []
    for r in rows:
        comp = companies.get(r.company_id)
        cont = contacts.get(r.contact_id)
        rep = reps.get(r.assigned_rep_id) if r.assigned_rep_id else None
        items.append(LeadListItem(
            id=r.id,
            business_id=r.business_id,
            company_name=comp.name if comp else "?",
            contact_email=cont.email if cont else "?",
            source=r.source.value,
            status=r.status.value,
            current_score=r.current_score,
            current_score_category=r.current_score_category.value if r.current_score_category else None,
            assigned_rep_name=rep.full_name if rep else None,
            created_at=r.created_at.isoformat(),
        ))

    return LeadListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/stats/summary")
def lead_summary(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Quick aggregated stats (used by the dashboard header)."""
    by_status = dict(
        db.query(Lead.status, func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True))
        .group_by(Lead.status).all()
    )
    by_category = dict(
        db.query(Lead.current_score_category, func.count(Lead.id))
        .filter(Lead.is_baseline.is_(True))
        .group_by(Lead.current_score_category).all()
    )
    total = db.query(func.count(Lead.id)).filter(Lead.is_baseline.is_(True)).scalar() or 0

    return {
        "total_leads": total,
        "by_status": {k.value if hasattr(k, "value") else str(k): v for k, v in by_status.items()},
        "by_category": {k.value if hasattr(k, "value") else str(k): v for k, v in by_category.items()},
    }


@router.get("/{business_id}", response_model=LeadDetail)
def get_lead(
    business_id: str,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> LeadDetail:
    lead = db.query(Lead).filter(Lead.business_id == business_id).one_or_none()
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {business_id} not found")

    company = db.query(Company).filter(Company.id == lead.company_id).one_or_none()
    contact = db.query(Contact).filter(Contact.id == lead.contact_id).one_or_none()
    rep = db.query(SalesRep).filter(SalesRep.id == lead.assigned_rep_id).one_or_none() if lead.assigned_rep_id else None

    # Latest score with contributions
    latest_score = (
        db.query(LeadScoreHistory)
        .filter(LeadScoreHistory.lead_id == lead.id)
        .order_by(desc(LeadScoreHistory.scored_at))
        .first()
    )
    score_detail = None
    if latest_score:
        try:
            contribs = json.loads(latest_score.contributions_json)
        except Exception:
            contribs = []
        score_detail = ScoreDetail(
            total=latest_score.total_score,
            category=latest_score.score_category.value,
            fit=latest_score.fit_score,
            intent=latest_score.intent_score,
            engagement=latest_score.engagement_score,
            recency=latest_score.recency_score,
            rule_version=latest_score.rule_version,
            scored_at=latest_score.scored_at.isoformat(),
            contributions=[ScoreContribution(**c) for c in contribs],
        )

    # Consent (latest per channel)
    latest_consents: dict[str, str] = {}
    for c in db.query(Consent).filter(Consent.lead_id == lead.id).order_by(Consent.changed_at.asc()).all():
        latest_consents[c.channel.value] = c.status.value
    consents = [ConsentDetail(channel=ch, status=st) for ch, st in latest_consents.items()]

    # Related counts
    tasks_count = db.query(func.count(Task.id)).filter(Task.lead_id == lead.id).scalar() or 0
    opp = db.query(Opportunity).filter(Opportunity.lead_id == lead.id).one_or_none()
    assignment_count = db.query(func.count(LeadAssignmentHistory.id)).filter(LeadAssignmentHistory.lead_id == lead.id).scalar() or 0

    return LeadDetail(
        id=lead.id,
        business_id=lead.business_id,
        source=lead.source.value,
        status=lead.status.value,
        company={
            "name": company.name if company else None,
            "industry": company.industry if company else None,
            "employee_count": company.employee_count if company else None,
            "annual_revenue_usd": float(company.annual_revenue_usd) if company else None,
            "country": company.country if company else None,
        },
        contact={
            "first_name": contact.first_name if contact else None,
            "last_name": contact.last_name if contact else None,
            "email": contact.email if contact else None,
            "title": contact.title if contact else None,
        },
        assigned_rep=(
            {"id": rep.id, "full_name": rep.full_name, "email": rep.email, "workload": rep.current_workload}
            if rep else None
        ),
        territory_id=lead.territory_id,
        product_interest=lead.product_interest,
        current_score=lead.current_score,
        current_score_category=lead.current_score_category.value if lead.current_score_category else None,
        created_at=lead.created_at.isoformat(),
        converted_at=lead.converted_at.isoformat() if lead.converted_at else None,
        score_detail=score_detail,
        consents=consents,
        tasks_count=tasks_count,
        opportunity_id=opp.id if opp else None,
        assignment_history_count=assignment_count,
    )
